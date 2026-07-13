from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.orm import Session

from .catalog_models import (
    DataSource,
    InstitutionKind,
    MonitoringStatus,
    OwnershipType,
    SourceHealth,
    University,
    UniversityCategory,
    UniversityCategoryLink,
)
from .json_validation import JsonDocumentError, load_and_validate_json, load_json_document, validate_json_document
from .university_repository import (
    add_category,
    add_category_link,
    add_data_source,
    add_university,
    get_university_for_export,
    list_categories,
    list_universities_for_import,
)

BACKEND_DIR = Path(__file__).resolve().parents[1]
CANONICAL_RESEARCH_PATH = BACKEND_DIR / "data" / "research" / "universities-canonical-2026.json"
CANONICAL_SCHEMA_PATH = BACKEND_DIR / "data" / "research" / "universities-canonical.schema.json"
UNIVERSITY_DOCUMENT_SCHEMA_PATH = BACKEND_DIR / "data" / "schemas" / "university-import.schema.json"

CATEGORY_LABELS: dict[str, str] = {
    "it": "IT",
    "technical": "Технический",
    "economic": "Экономический",
    "medical": "Медицинский",
    "pedagogical": "Педагогический",
    "agricultural": "Сельскохозяйственный",
    "arts": "Искусство и культура",
    "sports": "Спортивный",
    "military": "Военный",
    "humanities": "Гуманитарный",
    "law": "Право",
    "transport": "Транспортный",
    "emergency_services": "Службы чрезвычайных ситуаций",
    "general": "Многопрофильный",
    "private": "Частный",
    "other": "Другой",
}

RESEARCH_MONITORING_MAP: dict[str, MonitoringStatus] = {
    "online": MonitoringStatus.ONLINE,
    "candidate": MonitoringStatus.NEEDS_REVIEW,
    "reference_only": MonitoringStatus.REFERENCE_ONLY,
    "needs_research": MonitoringStatus.NEEDS_REVIEW,
}

REFERENCE_SOURCE_TYPES = frozenset({"official_registry", "official_site", "admissions"})
TRACKING_QUERY_KEYS = frozenset({"fbclid", "gclid", "yclid"})


class CatalogImportError(RuntimeError):
    pass


class CatalogValidationError(CatalogImportError):
    pass


class CatalogConflictError(CatalogImportError):
    def __init__(self, conflicts: list[str]) -> None:
        self.conflicts = conflicts
        super().__init__("Catalog import conflicts: " + "; ".join(conflicts))


@dataclass(frozen=True)
class ImportSource:
    source_type: str
    source_url: str
    source_checked_at: datetime


@dataclass(frozen=True)
class UniversityImportRecord:
    code: str
    slug: str
    short_name: str
    full_name: str
    institution_kind: InstitutionKind
    ownership_type: OwnershipType
    city: str
    region: str
    official_site_url: str
    admissions_url: str | None
    monitoring_status: MonitoringStatus
    active: bool
    source_url: str
    source_checked_at: datetime
    data_verified_at: datetime | None
    categories: tuple[str, ...]
    sources: tuple[ImportSource, ...]
    readonly_programs: tuple[dict[str, Any], ...] = ()
    source_creation_types: frozenset[str] = REFERENCE_SOURCE_TYPES


@dataclass(frozen=True)
class ImportSummary:
    dry_run: bool
    input_universities: int
    created: int
    updated: int
    unchanged: int
    conflicts: int
    categories_created: int
    categories_updated: int
    links_created: int
    sources_created: int
    protected_by_newer_verification: int
    review_items_skipped: int

    def as_dict(self) -> dict[str, int | bool]:
        return {
            "dry_run": self.dry_run,
            "input_universities": self.input_universities,
            "created": self.created,
            "updated": self.updated,
            "unchanged": self.unchanged,
            "conflicts": self.conflicts,
            "categories_created": self.categories_created,
            "categories_updated": self.categories_updated,
            "links_created": self.links_created,
            "sources_created": self.sources_created,
            "protected_by_newer_verification": self.protected_by_newer_verification,
            "review_items_skipped": self.review_items_skipped,
        }


@dataclass
class _ImportPlan:
    records: list[UniversityImportRecord]
    existing_by_code: dict[str, University]
    category_by_code: dict[str, UniversityCategory]
    creates: list[UniversityImportRecord] = field(default_factory=list)
    updates: list[tuple[University, dict[str, object]]] = field(default_factory=list)
    category_creates: list[str] = field(default_factory=list)
    category_updates: list[tuple[UniversityCategory, str]] = field(default_factory=list)
    link_creates: list[tuple[str, str]] = field(default_factory=list)
    source_creates: list[tuple[str, ImportSource]] = field(default_factory=list)
    protected: int = 0


def _enum_value(value: object) -> object:
    return value.value if hasattr(value, "value") else value


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _parse_datetime(value: str | None, field_name: str) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CatalogValidationError(f"{field_name} must be a valid date-time") from exc
    if parsed.tzinfo is None:
        raise CatalogValidationError(f"{field_name} must include a UTC offset")
    return parsed.astimezone(UTC)


def _iso_utc(value: datetime | None) -> str | None:
    normalized = _as_utc(value)
    return normalized.isoformat().replace("+00:00", "Z") if normalized is not None else None


def normalize_url(value: str) -> str:
    candidate = value.strip()
    parsed = urlsplit(candidate)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise CatalogValidationError(f"Invalid official URL: {value!r}")
    if parsed.username or parsed.password:
        raise CatalogValidationError("Official URLs must not contain credentials")
    scheme = parsed.scheme.lower()
    host = parsed.hostname.lower()
    try:
        port = parsed.port
    except ValueError as exc:
        raise CatalogValidationError(f"Invalid URL port: {value!r}") from exc
    default_port = (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    netloc = host if port is None or default_port else f"{host}:{port}"
    path = parsed.path or "/"
    query_items = [
        (key, item)
        for key, item in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in TRACKING_QUERY_KEYS
    ]
    query = urlencode(sorted(query_items), doseq=True)
    return urlunsplit((scheme, netloc, path, query, ""))


def _canonical_consistency_errors(data: dict[str, Any]) -> list[str]:
    universities = data.get("universities", [])
    review_items = data.get("review_items", [])
    if not isinstance(universities, list) or not isinstance(review_items, list):
        return ["Canonical universities and review_items must be arrays"]
    confirmed = [item for item in universities if item.get("active_status") == "confirmed"]
    expected_summary = {
        "confirmed_total": len(confirmed),
        "state_total": sum(item.get("ownership_type") == "state" for item in confirmed),
        "private_total": sum(item.get("ownership_type") == "private" for item in confirmed),
        "cities_total": len({item.get("city") for item in confirmed}),
        "with_admissions_url": sum(item.get("admissions_url") is not None for item in confirmed),
        "monitoring_candidates": sum(
            item.get("automation_assessment", {}).get("current_monitoring_status") == "candidate"
            for item in confirmed
        ),
        "online_monitoring": sum(
            item.get("automation_assessment", {}).get("current_monitoring_status") == "online"
            for item in confirmed
        ),
        "needs_review": len(review_items),
    }
    errors: list[str] = []
    if data.get("summary") != expected_summary:
        errors.append("Canonical summary does not match the universities/review_items arrays")
    for field_name in ("code", "slug"):
        duplicates = sorted(
            value for value, count in Counter(item.get(field_name) for item in confirmed).items() if count > 1
        )
        if duplicates:
            errors.append(f"Duplicate canonical {field_name}: {', '.join(str(item) for item in duplicates)}")
    online = [
        item.get("code")
        for item in confirmed
        if item.get("automation_assessment", {}).get("current_monitoring_status") == "online"
    ]
    if online != ["bseu"]:
        errors.append(f"Only bseu may be online, got {online}")
    review_names = {item.get("name") for item in review_items}
    overlap = [item.get("code") for item in confirmed if item.get("full_name") in review_names]
    if overlap:
        errors.append(f"Review items leaked into confirmed universities: {overlap}")
    return errors


def _record_from_canonical(item: dict[str, Any]) -> UniversityImportRecord:
    checked_at = _parse_datetime(item["source_checked_at"], f"{item['code']}.source_checked_at")
    assert checked_at is not None
    monitoring = RESEARCH_MONITORING_MAP[item["automation_assessment"]["current_monitoring_status"]]
    sources = [
        ImportSource("official_registry", normalize_url(item["official_registry_url"]), checked_at),
        ImportSource("official_site", normalize_url(item["official_site_url"]), checked_at),
    ]
    if item["admissions_url"] is not None:
        sources.append(ImportSource("admissions", normalize_url(item["admissions_url"]), checked_at))
    return UniversityImportRecord(
        code=item["code"],
        slug=item["slug"],
        short_name=item["short_name"],
        full_name=item["full_name"],
        institution_kind=InstitutionKind(item["institution_kind"]),
        ownership_type=OwnershipType(item["ownership_type"]),
        city=item["city"],
        region=item["region"],
        official_site_url=normalize_url(item["official_site_url"]),
        admissions_url=normalize_url(item["admissions_url"]) if item["admissions_url"] else None,
        monitoring_status=monitoring,
        active=True,
        source_url=normalize_url(item["official_registry_url"]),
        source_checked_at=checked_at,
        data_verified_at=checked_at,
        categories=tuple(sorted(item["categories"])),
        sources=tuple(sorted(sources, key=lambda source: (source.source_type, source.source_url))),
    )


def load_canonical_records(path: Path = CANONICAL_RESEARCH_PATH) -> tuple[list[UniversityImportRecord], int]:
    try:
        data = load_and_validate_json(path, CANONICAL_SCHEMA_PATH)
    except JsonDocumentError as exc:
        raise CatalogValidationError(str(exc)) from exc
    if not isinstance(data, dict):
        raise CatalogValidationError("Canonical research root must be an object")
    errors = _canonical_consistency_errors(data)
    if errors:
        raise CatalogValidationError("; ".join(errors))
    records = [
        _record_from_canonical(item)
        for item in data["universities"]
        if item["active_status"] == "confirmed"
    ]
    return records, len(data["review_items"])


def _university_changes(existing: University, record: UniversityImportRecord) -> tuple[dict[str, object], bool]:
    existing_verified = _as_utc(existing.data_verified_at)
    incoming_verified = _as_utc(record.data_verified_at or record.source_checked_at)
    if existing_verified is not None and incoming_verified is not None and existing_verified > incoming_verified:
        return {}, True

    desired: dict[str, object | None] = {
        "short_name": record.short_name,
        "full_name": record.full_name,
        "institution_kind": record.institution_kind,
        "ownership_type": record.ownership_type,
        "city": record.city,
        "region": record.region,
        "official_site_url": record.official_site_url,
        "admissions_url": record.admissions_url,
        "monitoring_status": record.monitoring_status,
        "active": record.active,
        "source_url": record.source_url,
        "source_checked_at": record.source_checked_at,
        "data_verified_at": record.data_verified_at,
    }
    if existing.code == "bseu" and _enum_value(existing.monitoring_status) == MonitoringStatus.ONLINE.value:
        desired["monitoring_status"] = MonitoringStatus.ONLINE
    changes: dict[str, object] = {}
    for field_name, incoming in desired.items():
        if incoming is None:
            continue
        current = getattr(existing, field_name)
        if isinstance(incoming, datetime):
            equal = _as_utc(current) == _as_utc(incoming)
        else:
            equal = _enum_value(current) == _enum_value(incoming)
        if not equal:
            changes[field_name] = incoming
    return changes, False


def _source_identity(source_type: str, source_url: str) -> tuple[str, str]:
    return source_type, normalize_url(source_url)


def _build_plan(session: Session, records: list[UniversityImportRecord]) -> _ImportPlan:
    existing = list_universities_for_import(session)
    existing_by_code = {item.code: item for item in existing}
    existing_by_slug = {item.slug: item for item in existing}
    category_by_code = {item.code: item for item in list_categories(session)}
    plan = _ImportPlan(records=records, existing_by_code=existing_by_code, category_by_code=category_by_code)

    conflicts: list[str] = []
    input_codes = Counter(record.code for record in records)
    input_slugs = Counter(record.slug for record in records)
    conflicts.extend(f"duplicate input code {code}" for code, count in input_codes.items() if count > 1)
    conflicts.extend(f"duplicate input slug {slug}" for slug, count in input_slugs.items() if count > 1)
    for record in records:
        by_code = existing_by_code.get(record.code)
        by_slug = existing_by_slug.get(record.slug)
        if by_code is not None and by_code.slug != record.slug:
            conflicts.append(f"code {record.code} already uses slug {by_code.slug}, not {record.slug}")
        if by_slug is not None and by_slug.code != record.code:
            conflicts.append(f"slug {record.slug} already belongs to code {by_slug.code}")
        if record.monitoring_status == MonitoringStatus.ONLINE and record.code != "bseu":
            conflicts.append(f"only bseu may be online, got {record.code}")
        if record.code == "bseu" and record.monitoring_status != MonitoringStatus.ONLINE:
            conflicts.append("bseu must remain online")
        if record.code == "bseu" and by_code is not None and by_code.id != 1:
            conflicts.append(f"bseu must preserve University ID 1, got {by_code.id}")
    if conflicts:
        raise CatalogConflictError(sorted(set(conflicts)))

    for category_code in sorted({code for record in records for code in record.categories}):
        if category_code not in CATEGORY_LABELS:
            raise CatalogValidationError(f"Unknown category code: {category_code}")
        category = category_by_code.get(category_code)
        if category is None:
            plan.category_creates.append(category_code)
        elif category.label_ru != CATEGORY_LABELS[category_code]:
            plan.category_updates.append((category, CATEGORY_LABELS[category_code]))

    for record in records:
        university = existing_by_code.get(record.code)
        if university is None:
            plan.creates.append(record)
            existing_categories: set[str] = set()
            existing_sources: set[tuple[str, str]] = set()
        else:
            changes, protected = _university_changes(university, record)
            if changes:
                plan.updates.append((university, changes))
            if protected:
                plan.protected += 1
            existing_categories = {category.code for category in university.categories}
            existing_sources = {
                _source_identity(source.source_type, source.source_url) for source in university.data_sources
            }
        for category_code in record.categories:
            if category_code not in existing_categories:
                plan.link_creates.append((record.code, category_code))
        for source in record.sources:
            identity = _source_identity(source.source_type, source.source_url)
            if identity in existing_sources:
                continue
            if source.source_type not in record.source_creation_types:
                conflicts.append(
                    f"{record.code}: source type {source.source_type} is read-only and does not already exist"
                )
                continue
            plan.source_creates.append((record.code, source))
            existing_sources.add(identity)
    if conflicts:
        raise CatalogConflictError(sorted(set(conflicts)))
    return plan


def _new_university(record: UniversityImportRecord) -> University:
    return University(
        code=record.code,
        slug=record.slug,
        short_name=record.short_name,
        full_name=record.full_name,
        institution_kind=record.institution_kind,
        ownership_type=record.ownership_type,
        city=record.city,
        region=record.region,
        official_site_url=record.official_site_url,
        admissions_url=record.admissions_url,
        monitoring_status=record.monitoring_status,
        active=record.active,
        source_url=record.source_url,
        source_checked_at=record.source_checked_at,
        data_verified_at=record.data_verified_at,
    )


def _apply_plan(session: Session, plan: _ImportPlan) -> None:
    for code in plan.category_creates:
        category = UniversityCategory(code=code, label_ru=CATEGORY_LABELS[code])
        add_category(session, category)
        plan.category_by_code[code] = category
    for category, label in plan.category_updates:
        category.label_ru = label

    for record in plan.creates:
        university = _new_university(record)
        add_university(session, university)
        plan.existing_by_code[record.code] = university
    for university, changes in plan.updates:
        for field_name, value in changes.items():
            setattr(university, field_name, value)
    session.flush()

    for university_code, category_code in plan.link_creates:
        university = plan.existing_by_code[university_code]
        category = plan.category_by_code[category_code]
        add_category_link(
            session,
            UniversityCategoryLink(university_id=university.id, category_id=category.id),
        )
    for university_code, source in plan.source_creates:
        university = plan.existing_by_code[university_code]
        add_data_source(
            session,
            DataSource(
                university_id=university.id,
                source_type=source.source_type,
                source_url=source.source_url,
                adapter_name=None,
                refresh_interval_minutes=None,
                enabled=True,
                health_status=SourceHealth.UNKNOWN,
            ),
        )
    session.flush()


def _summary(plan: _ImportPlan, *, dry_run: bool, review_items_skipped: int) -> ImportSummary:
    unchanged = len(plan.records) - len(plan.creates) - len(plan.updates)
    return ImportSummary(
        dry_run=dry_run,
        input_universities=len(plan.records),
        created=len(plan.creates),
        updated=len(plan.updates),
        unchanged=unchanged,
        conflicts=0,
        categories_created=len(plan.category_creates),
        categories_updated=len(plan.category_updates),
        links_created=len(plan.link_creates),
        sources_created=len(plan.source_creates),
        protected_by_newer_verification=plan.protected,
        review_items_skipped=review_items_skipped,
    )


def import_records(
    session: Session,
    records: list[UniversityImportRecord],
    *,
    dry_run: bool,
    review_items_skipped: int = 0,
) -> ImportSummary:
    plan = _build_plan(session, records)
    if not dry_run:
        _apply_plan(session, plan)
    return _summary(plan, dry_run=dry_run, review_items_skipped=review_items_skipped)


def seed_universities(
    session: Session,
    *,
    path: Path = CANONICAL_RESEARCH_PATH,
    dry_run: bool = False,
) -> ImportSummary:
    records, review_items_skipped = load_canonical_records(path)
    return import_records(
        session,
        records,
        dry_run=dry_run,
        review_items_skipped=review_items_skipped,
    )


def _record_from_university_document(document: dict[str, Any]) -> UniversityImportRecord:
    value = document["university"]
    checked_at = _parse_datetime(value["source_checked_at"], "university.source_checked_at")
    assert checked_at is not None
    verified_at = _parse_datetime(value["data_verified_at"], "university.data_verified_at")
    provenance = document["provenance"]
    if normalize_url(provenance["source_url"]) != normalize_url(value["source_url"]):
        raise CatalogValidationError("provenance.source_url must match university.source_url")
    if _parse_datetime(provenance["source_checked_at"], "provenance.source_checked_at") != checked_at:
        raise CatalogValidationError("provenance.source_checked_at must match university.source_checked_at")
    if _parse_datetime(provenance["data_verified_at"], "provenance.data_verified_at") != verified_at:
        raise CatalogValidationError("provenance.data_verified_at must match university.data_verified_at")

    categories: list[str] = []
    for category in document["categories"]:
        code = category["code"]
        expected_label = CATEGORY_LABELS.get(code)
        if expected_label is None or category["label_ru"] != expected_label:
            raise CatalogValidationError(f"Category {code} must use canonical label {expected_label!r}")
        categories.append(code)

    sources: list[ImportSource] = []
    for source in document["sources"]:
        source_checked_at = _parse_datetime(source["source_checked_at"], "sources[].source_checked_at")
        assert source_checked_at is not None
        sources.append(
            ImportSource(
                source_type=source["source_type"],
                source_url=normalize_url(source["source_url"]),
                source_checked_at=source_checked_at,
            )
        )
    identities = [(source.source_type, source.source_url) for source in sources]
    if len(identities) != len(set(identities)):
        raise CatalogValidationError("University document contains duplicate data sources")

    expected_sources = {
        ("official_registry", normalize_url(value["source_url"])),
        ("official_site", normalize_url(value["official_site_url"])),
    }
    if value["admissions_url"] is not None:
        expected_sources.add(("admissions", normalize_url(value["admissions_url"])))
    if not expected_sources.issubset(set(identities)):
        raise CatalogValidationError("University document lacks required registry/site/admissions sources")

    return UniversityImportRecord(
        code=value["code"],
        slug=value["slug"],
        short_name=value["short_name"],
        full_name=value["full_name"],
        institution_kind=InstitutionKind(value["institution_kind"]),
        ownership_type=OwnershipType(value["ownership_type"]),
        city=value["city"],
        region=value["region"],
        official_site_url=normalize_url(value["official_site_url"]),
        admissions_url=normalize_url(value["admissions_url"]) if value["admissions_url"] else None,
        monitoring_status=MonitoringStatus(value["monitoring_status"]),
        active=value["active"],
        source_url=normalize_url(value["source_url"]),
        source_checked_at=checked_at,
        data_verified_at=verified_at,
        categories=tuple(sorted(set(categories))),
        sources=tuple(sorted(sources, key=lambda source: (source.source_type, source.source_url))),
        readonly_programs=tuple(document["programs"]),
    )


def _offering_export(offering) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    return {
        "id": offering.id,
        "admission_year": offering.admission_year,
        "study_form": _enum_value(offering.study_form),
        "funding_type": _enum_value(offering.funding_type),
        "places": offering.places,
        "application_deadline": _iso_utc(offering.application_deadline),
        "monitoring_supported": offering.monitoring_supported,
        "monitoring_status": _enum_value(offering.monitoring_status),
        "official_url": offering.official_url,
        "source_url": offering.source_url,
        "source_checked_at": _iso_utc(offering.source_checked_at),
    }


def export_university_document(session: Session, slug: str) -> dict[str, Any]:
    university = get_university_for_export(session, slug)
    if university is None:
        raise CatalogValidationError(f"University not found: {slug}")
    sources = []
    for source in sorted(university.data_sources, key=lambda item: (item.source_type, item.source_url)):
        checked_at = source.last_success_at or source.last_attempt_at or university.source_checked_at
        sources.append(
            {
                "source_type": source.source_type,
                "source_url": source.source_url,
                "source_checked_at": _iso_utc(checked_at),
            }
        )
    programs = [
        {
            "id": program.id,
            "code": program.code,
            "slug": program.slug,
            "name": program.name,
            "qualification": program.qualification,
            "faculty_name": program.faculty_name,
            "official_url": program.official_url,
            "source_checked_at": _iso_utc(program.source_checked_at),
            "offerings": [
                _offering_export(offering)
                for offering in sorted(
                    program.offerings,
                    key=lambda item: (item.admission_year, str(_enum_value(item.study_form)), item.id),
                )
            ],
        }
        for program in sorted(university.programs, key=lambda item: (item.slug, item.id))
    ]
    document = {
        "schema_version": "1.0",
        "university": {
            "code": university.code,
            "slug": university.slug,
            "short_name": university.short_name,
            "full_name": university.full_name,
            "institution_kind": _enum_value(university.institution_kind),
            "ownership_type": _enum_value(university.ownership_type),
            "city": university.city,
            "region": university.region,
            "official_site_url": university.official_site_url,
            "admissions_url": university.admissions_url,
            "monitoring_status": _enum_value(university.monitoring_status),
            "active": university.active,
            "source_url": university.source_url,
            "source_checked_at": _iso_utc(university.source_checked_at),
            "data_verified_at": _iso_utc(university.data_verified_at),
        },
        "categories": [
            {"code": category.code, "label_ru": category.label_ru}
            for category in sorted(university.categories, key=lambda item: item.code)
        ],
        "sources": sources,
        "programs": programs,
        "provenance": {
            "source_url": university.source_url,
            "source_checked_at": _iso_utc(university.source_checked_at),
            "data_verified_at": _iso_utc(university.data_verified_at),
        },
    }
    schema = load_json_document(UNIVERSITY_DOCUMENT_SCHEMA_PATH)
    try:
        validate_json_document(document, schema)
    except JsonDocumentError as exc:
        raise CatalogValidationError(f"Generated export does not pass its schema: {exc}") from exc
    return document


def import_university_document(session: Session, path: Path, *, dry_run: bool = False) -> ImportSummary:
    try:
        document = load_and_validate_json(path, UNIVERSITY_DOCUMENT_SCHEMA_PATH)
    except JsonDocumentError as exc:
        raise CatalogValidationError(str(exc)) from exc
    if not isinstance(document, dict):
        raise CatalogValidationError("University import root must be an object")
    record = _record_from_university_document(document)
    if record.readonly_programs:
        current = get_university_for_export(session, record.slug)
        if current is None:
            raise CatalogConflictError(["programs/offerings are read-only and cannot be created by import-university"])
        current_document = export_university_document(session, record.slug)
        if current_document["programs"] != list(record.readonly_programs):
            raise CatalogConflictError(["programs/offerings differ from the existing read-only catalog state"])
    return import_records(session, [record], dry_run=dry_run)
