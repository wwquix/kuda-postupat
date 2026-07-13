from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .catalog_import_service import (
    CANONICAL_RESEARCH_PATH,
    CATEGORY_LABELS,
    CatalogImportError,
    UniversityImportRecord,
    load_canonical_records,
    normalize_url,
)
from .catalog_models import DataSource, MonitoringStatus, Program, ProgramOffering, University
from .json_validation import load_json_document
from .university_repository import (
    CatalogSummary,
    catalog_summary,
    duplicate_category_links,
    duplicate_data_sources,
    duplicate_values,
    list_categories,
    list_data_sources,
    list_universities_for_import,
)


@dataclass(frozen=True)
class CatalogAuditResult:
    summary: CatalogSummary
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict[str, object]:
        return {
            "status": "ok" if self.ok else "error",
            "summary": self.summary.as_dict(),
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


def _enum_value(value: object) -> object:
    return value.value if hasattr(value, "value") else value


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _url_is_valid(value: str | None) -> bool:
    if value is None:
        return True
    try:
        normalize_url(value)
    except CatalogImportError:
        return False
    return True


def _record_mismatches(university: University, record: UniversityImportRecord) -> list[str]:
    desired: dict[str, object | None] = {
        "slug": record.slug,
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
    }
    mismatches: list[str] = []
    for field_name, expected in desired.items():
        if expected is None:
            continue
        actual = getattr(university, field_name)
        if field_name.endswith("_url") or field_name == "source_url":
            equal = normalize_url(str(actual)) == normalize_url(str(expected))
        else:
            equal = _enum_value(actual) == _enum_value(expected)
        if not equal:
            mismatches.append(field_name)
    checked_at = _as_utc(university.source_checked_at)
    if checked_at is None or checked_at < record.source_checked_at:
        mismatches.append("source_checked_at")
    return mismatches


def _expected_source_identities(record: UniversityImportRecord) -> set[tuple[str, str]]:
    return {(source.source_type, normalize_url(source.source_url)) for source in record.sources}


def _source_identities(university: University) -> set[tuple[str, str]]:
    return {(source.source_type, normalize_url(source.source_url)) for source in university.data_sources}


def audit_catalog(
    session: Session,
    *,
    canonical_path: Path = CANONICAL_RESEARCH_PATH,
) -> CatalogAuditResult:
    records, _review_count = load_canonical_records(canonical_path)
    summary = catalog_summary(session)
    universities = list_universities_for_import(session)
    by_code = {university.code: university for university in universities}
    errors: list[str] = []
    warnings: list[str] = []

    duplicate_codes = duplicate_values(session, University.code)
    duplicate_slugs = duplicate_values(session, University.slug)
    if duplicate_codes:
        errors.append(f"Duplicate university codes: {', '.join(duplicate_codes)}")
    if duplicate_slugs:
        errors.append(f"Duplicate university slugs: {', '.join(duplicate_slugs)}")
    duplicate_links = duplicate_category_links(session)
    if duplicate_links:
        errors.append(f"Duplicate category links: {', '.join(duplicate_links)}")
    duplicate_sources = duplicate_data_sources(session)
    if duplicate_sources:
        errors.append(f"Duplicate data sources: {', '.join(duplicate_sources)}")

    required_fields = ("code", "slug", "short_name", "full_name", "official_site_url", "source_url")
    for university in universities:
        missing = [
            field_name
            for field_name in required_fields
            if not str(getattr(university, field_name) or "").strip()
        ]
        if missing:
            errors.append(f"{university.code or university.id}: empty required fields: {', '.join(missing)}")
        urls = [university.official_site_url, university.admissions_url, university.source_url]
        if any(not _url_is_valid(url) for url in urls):
            errors.append(f"{university.code}: invalid University URL")
        if university.source_checked_at is None:
            errors.append(f"{university.code}: missing source_checked_at")
        registry_sources = [source for source in university.data_sources if source.source_type == "official_registry"]
        if not registry_sources:
            errors.append(f"{university.code}: missing official_registry DataSource")
        if _enum_value(university.monitoring_status) == MonitoringStatus.ONLINE.value and university.code != "bseu":
            errors.append(f"{university.code}: unsupported university is marked online")

    categories = list_categories(session)
    for category in categories:
        if not category.code.strip() or not category.label_ru.strip():
            errors.append(f"Category {category.id} has an empty code or label")
        expected_label = CATEGORY_LABELS.get(category.code)
        if expected_label is not None and category.label_ru != expected_label:
            errors.append(f"Category {category.code} has non-canonical label {category.label_ru!r}")

    for source in list_data_sources(session):
        if not _url_is_valid(source.source_url):
            errors.append(f"DataSource {source.id} has an invalid URL")
        university = by_code.get(source.university.code) if source.university is not None else None
        has_checked_time = source.last_attempt_at or source.last_success_at or (
            university.source_checked_at if university is not None else None
        )
        if has_checked_time is None:
            errors.append(f"DataSource {source.id} has no source check time")

    expected_codes = {record.code for record in records}
    for record in records:
        university = by_code.get(record.code)
        if university is None:
            errors.append(f"Canonical university missing from catalog: {record.code}")
            continue
        mismatches = _record_mismatches(university, record)
        if mismatches:
            newer_manual = _as_utc(university.data_verified_at)
            if newer_manual is not None and newer_manual > record.source_checked_at:
                warnings.append(
                    f"{record.code}: newer verified catalog values differ from canonical fields: "
                    f"{', '.join(mismatches)}"
                )
            else:
                errors.append(f"{record.code}: canonical field mismatch: {', '.join(mismatches)}")
        category_codes = {category.code for category in university.categories}
        missing_categories = set(record.categories) - category_codes
        if missing_categories:
            errors.append(f"{record.code}: missing categories: {', '.join(sorted(missing_categories))}")
        missing_sources = _expected_source_identities(record) - _source_identities(university)
        if missing_sources:
            formatted = ", ".join(f"{kind}:{url}" for kind, url in sorted(missing_sources))
            errors.append(f"{record.code}: missing canonical sources: {formatted}")

    extra_codes = sorted(set(by_code) - expected_codes)
    if extra_codes:
        warnings.append(f"Catalog has rows outside the canonical dataset: {', '.join(extra_codes)}")

    raw_research = load_json_document(canonical_path)
    review_names = {item["name"] for item in raw_research["review_items"]}
    leaked_review_items = sorted(
        university.code
        for university in universities
        if university.full_name in review_names or university.short_name in review_names
    )
    if leaked_review_items:
        errors.append(f"Review items leaked into production catalog: {', '.join(leaked_review_items)}")

    bseu = by_code.get("bseu")
    if bseu is None:
        errors.append("BSEU is missing")
    else:
        if bseu.id != 1:
            errors.append(f"BSEU University ID changed: {bseu.id}")
        if _enum_value(bseu.monitoring_status) != MonitoringStatus.ONLINE.value:
            errors.append("BSEU is not online")
        programs = list(session.scalars(select(Program).where(Program.university_id == bseu.id)).all())
        if not programs:
            errors.append("BSEU has no catalog Program")
        program_ids = [program.id for program in programs]
        offerings = list(
            session.scalars(select(ProgramOffering).where(ProgramOffering.program_id.in_(program_ids))).all()
        )
        if not offerings:
            errors.append("BSEU has no catalog ProgramOffering")
        xml_source = session.scalar(
            select(DataSource).where(
                DataSource.university_id == bseu.id,
                DataSource.source_type == "admission_xml",
            )
        )
        if xml_source is None or xml_source.adapter_name != "legacy_admission_scraper":
            errors.append("BSEU XML DataSource adapter identity is missing")

    if summary.universities_total != 47:
        errors.append(f"Expected 47 universities, got {summary.universities_total}")
    if summary.ownership_totals.get("state", 0) != 43:
        errors.append(f"Expected 43 state universities, got {summary.ownership_totals.get('state', 0)}")
    if summary.ownership_totals.get("private", 0) != 4:
        errors.append(f"Expected 4 private universities, got {summary.ownership_totals.get('private', 0)}")
    if summary.cities_total != 11:
        errors.append(f"Expected 11 cities, got {summary.cities_total}")
    if summary.with_admissions_url != 33:
        errors.append(f"Expected 33 admissions URLs, got {summary.with_admissions_url}")
    if summary.monitoring_totals.get("online", 0) != 1:
        errors.append(f"Expected only one online university, got {summary.monitoring_totals.get('online', 0)}")

    missing_admissions = sorted(university.code for university in universities if university.admissions_url is None)
    if missing_admissions:
        warnings.append(f"Universities without a confirmed admissions URL: {', '.join(missing_admissions)}")
    universities_with_programs = set(session.scalars(select(Program.university_id)).all())
    without_programs = sorted(
        university.code for university in universities if university.id not in universities_with_programs
    )
    if without_programs:
        warnings.append(f"Universities without imported programs: {', '.join(without_programs)}")
    without_adapters = sorted(
        university.code
        for university in universities
        if not any(source.adapter_name for source in university.data_sources)
    )
    if without_adapters:
        warnings.append(f"Universities without an admission adapter: {', '.join(without_adapters)}")

    return CatalogAuditResult(
        summary=summary,
        errors=tuple(sorted(set(errors))),
        warnings=tuple(sorted(set(warnings))),
    )
