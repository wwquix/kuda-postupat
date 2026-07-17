from __future__ import annotations

import hashlib
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import URL, Engine, create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker

from .catalog_import_service import CatalogConflictError, CatalogValidationError
from .catalog_models import (
    DataSource,
    FundingType,
    LegacySpecialtyMapping,
    MonitoringStatus,
    Program,
    ProgramOffering,
    StudyForm,
    University,
)
from .json_validation import JsonDocumentError, load_and_validate_json
from .models import Specialty
from .schema import ensure_schema_current

ROOT_DIR = Path(__file__).resolve().parents[2]
AUDIT_PATH = ROOT_DIR / "docs" / "data" / "bseu-program-import-candidates.json"
AUDIT_SCHEMA_PATH = ROOT_DIR / "docs" / "data" / "bseu-program-import-candidates.schema.json"

BSEU_CODE = "bseu"
ECONOMIC_INFORMATICS_CODE = "6-05-0311-05"
ECONOMIC_INFORMATICS_SLUG = "economic-informatics"
ECONOMIC_INFORMATICS_NAME = "Экономическая информатика"
ADMISSION_XML_URL = "https://bseu.by/abiturient/xml/1.xml"
ADMISSION_PLAN_URL = "https://bseu.by/russian/abiturient/tsp2026.pdf"
EXPECTED_CONFIRMED = 57
EXPECTED_NEEDS_REVIEW = 20
EXPECTED_PROGRAMS = 17


@dataclass(frozen=True)
class OfferingRecord:
    candidate_key: str
    match_key: str
    admission_year: int
    study_form: StudyForm
    funding_type: FundingType
    places: int
    official_url: str
    source_url: str
    source_checked_at: datetime


@dataclass(frozen=True)
class ProgramRecord:
    match_key: str
    strategy: str
    source_spid: str
    slug: str
    code: str | None
    name: str
    faculty_name: str | None
    official_url: str
    source_checked_at: datetime
    offerings: tuple[OfferingRecord, ...]


@dataclass(frozen=True)
class BseuProgramAudit:
    programs: tuple[ProgramRecord, ...]
    confirmed_candidates: int
    needs_review_skipped: int


@dataclass(frozen=True)
class BseuProgramImportSummary:
    confirmed_candidates: int
    needs_review_skipped: int
    program_identities_expected: int
    programs_created: int
    programs_reused: int
    offerings_created: int
    offerings_reused: int
    conflicts: int
    writes_applied: bool

    def as_dict(self) -> dict[str, int | bool]:
        return {
            "confirmed_candidates": self.confirmed_candidates,
            "needs_review_skipped": self.needs_review_skipped,
            "program_identities_expected": self.program_identities_expected,
            "programs_created": self.programs_created,
            "programs_reused": self.programs_reused,
            "offerings_created": self.offerings_created,
            "offerings_reused": self.offerings_reused,
            "conflicts": self.conflicts,
            "writes_applied": self.writes_applied,
        }


@dataclass
class _ImportPlan:
    audit: BseuProgramAudit
    university: University
    programs_to_create: list[ProgramRecord] = field(default_factory=list)
    programs_reused: dict[str, Program] = field(default_factory=dict)
    offerings_to_create: list[tuple[ProgramRecord, OfferingRecord]] = field(default_factory=list)
    offerings_reused: dict[str, ProgramOffering] = field(default_factory=dict)


def _parse_datetime(value: str, field_name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CatalogValidationError(f"Invalid {field_name}: {value!r}") from exc
    if parsed.tzinfo is None:
        raise CatalogValidationError(f"{field_name} must include a timezone")
    return parsed.astimezone(UTC)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _normalized_name(value: str) -> str:
    return " ".join(value.split()).casefold()


def _program_slug(match_key: str) -> str:
    if match_key == f"bseu|code|{ECONOMIC_INFORMATICS_CODE}":
        return ECONOMIC_INFORMATICS_SLUG
    digest = hashlib.sha256(match_key.encode("utf-8")).hexdigest()[:20]
    return f"bseu-audit-{digest}"


def _candidate_official_url(candidate: dict[str, Any]) -> str:
    supplemental = candidate["supplemental_official_source_urls"]
    if supplemental:
        return supplemental[0]
    return candidate["official_source_url"]


def _audit_consistency_errors(data: dict[str, Any]) -> list[str]:
    candidates = data["candidates"]
    status_counts = Counter(candidate["status"] for candidate in candidates)
    errors: list[str] = []
    if len({candidate["candidate_key"] for candidate in candidates}) != len(candidates):
        errors.append("candidate keys are not unique")
    if (status_counts["confirmed"], status_counts["needs_review"], status_counts["unavailable"]) != (
        EXPECTED_CONFIRMED,
        EXPECTED_NEEDS_REVIEW,
        0,
    ):
        errors.append("tracked status scope must remain exactly 57 confirmed, 20 needs_review, 0 unavailable")
    summary = data["summary"]
    for status in ("confirmed", "needs_review", "unavailable"):
        if summary[status] != status_counts[status]:
            errors.append(f"summary.{status} does not match candidate rows")
    if summary["confirmed_program_identities"] != EXPECTED_PROGRAMS:
        errors.append("summary must declare exactly 17 confirmed Program identities")

    confirmed = [candidate for candidate in candidates if candidate["status"] == "confirmed"]
    program_keys = [candidate["proposed_program_identity"]["match_key"] for candidate in confirmed]
    offering_keys = [candidate["proposed_program_offering_identity"]["match_key"] for candidate in confirmed]
    if None in program_keys or len(set(program_keys)) != EXPECTED_PROGRAMS:
        errors.append("confirmed rows must resolve to exactly 17 non-null Program match keys")
    if None in offering_keys or len(set(offering_keys)) != EXPECTED_CONFIRMED:
        errors.append("confirmed rows must resolve to 57 unique non-null Offering match keys")

    for candidate in confirmed:
        source = candidate["source_identity"]
        program_identity = candidate["proposed_program_identity"]
        offering_identity = candidate["proposed_program_offering_identity"]
        expected_candidate_key = (
            f"bseu:2026:spid-{source['specialty_id']}:form-{source['study_form_id']}:funding-{source['funding_id']}"
        )
        if candidate["candidate_key"] != expected_candidate_key:
            errors.append(f"{candidate['candidate_key']}: source identity does not match candidate key")
        if program_identity["source_spid"] != source["specialty_id"]:
            errors.append(f"{candidate['candidate_key']}: Program source_spid mismatch")
        if offering_identity["program_match_key"] != program_identity["match_key"]:
            errors.append(f"{candidate['candidate_key']}: Offering points to a different Program match key")
        if offering_identity["admission_year"] != candidate["admission_year"]:
            errors.append(f"{candidate['candidate_key']}: admission year mismatch")
        if offering_identity["funding_type"] != candidate["funding_type"]:
            errors.append(f"{candidate['candidate_key']}: funding type mismatch")
        expected_form = data["derivation"]["study_form_mapping"][source["study_form_id"]]
        if offering_identity["study_form"] != expected_form:
            errors.append(f"{candidate['candidate_key']}: study form mapping mismatch")
        expected_funding = data["derivation"]["funding_mapping"][source["funding_id"]]
        if candidate["funding_type"] != expected_funding:
            errors.append(f"{candidate['candidate_key']}: funding mapping mismatch")
        if candidate["official_source_url"] != data["source"]["url"]:
            errors.append(f"{candidate['candidate_key']}: source URL differs from the audited source")
    return errors


def load_bseu_program_audit(
    audit_path: Path = AUDIT_PATH,
    schema_path: Path = AUDIT_SCHEMA_PATH,
) -> BseuProgramAudit:
    try:
        data = load_and_validate_json(audit_path, schema_path)
    except JsonDocumentError as exc:
        raise CatalogValidationError(str(exc)) from exc
    if not isinstance(data, dict):
        raise CatalogValidationError("BSEU Program audit root must be an object")
    errors = _audit_consistency_errors(data)
    if errors:
        raise CatalogValidationError("; ".join(sorted(set(errors))))

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in data["candidates"]:
        if candidate["status"] == "confirmed":
            grouped[candidate["proposed_program_identity"]["match_key"]].append(candidate)

    programs: list[ProgramRecord] = []
    group_errors: list[str] = []
    for match_key in sorted(grouped):
        candidates = grouped[match_key]
        stable_fields = {
            (
                candidate["program_name"],
                candidate["specialty_code"],
                candidate["faculty"],
                candidate["official_source_url"],
                candidate["source_checked_at"],
                candidate["proposed_program_identity"]["strategy"],
                candidate["proposed_program_identity"]["source_spid"],
            )
            for candidate in candidates
        }
        if len(stable_fields) != 1:
            group_errors.append(f"{match_key}: Program fields are inconsistent across confirmed candidates")
            continue
        name, code, faculty, official_url, checked_at, strategy, source_spid = stable_fields.pop()
        offerings = tuple(
            OfferingRecord(
                candidate_key=candidate["candidate_key"],
                match_key=candidate["proposed_program_offering_identity"]["match_key"],
                admission_year=candidate["admission_year"],
                study_form=StudyForm(candidate["proposed_program_offering_identity"]["study_form"]),
                funding_type=FundingType(candidate["funding_type"]),
                places=candidate["admission_plan"],
                official_url=_candidate_official_url(candidate),
                source_url=candidate["official_source_url"],
                source_checked_at=_parse_datetime(candidate["source_checked_at"], "source_checked_at"),
            )
            for candidate in sorted(
                candidates,
                key=lambda item: item["proposed_program_offering_identity"]["match_key"],
            )
        )
        programs.append(
            ProgramRecord(
                match_key=match_key,
                strategy=strategy,
                source_spid=source_spid,
                slug=_program_slug(match_key),
                code=code,
                name=name,
                faculty_name=faculty,
                official_url=official_url,
                source_checked_at=_parse_datetime(checked_at, "source_checked_at"),
                offerings=offerings,
            )
        )
    if group_errors:
        raise CatalogValidationError("; ".join(group_errors))
    return BseuProgramAudit(
        programs=tuple(programs),
        confirmed_candidates=EXPECTED_CONFIRMED,
        needs_review_skipped=EXPECTED_NEEDS_REVIEW,
    )


def _require_bseu(session: Session) -> University:
    universities = session.scalars(select(University).where(University.code == BSEU_CODE)).all()
    slug_rows = session.scalars(select(University).where(University.slug == BSEU_CODE)).all()
    conflicts: list[str] = []
    if len(universities) != 1:
        conflicts.append(f"expected exactly one University with code bseu, got {len(universities)}")
    if len(slug_rows) != 1:
        conflicts.append(f"expected exactly one University with slug bseu, got {len(slug_rows)}")
    if universities and slug_rows and universities[0].id != slug_rows[0].id:
        conflicts.append("BSEU code and slug identify different University rows")
    if universities and universities[0].id != 1:
        conflicts.append(f"canonical BSEU University must preserve ID 1, got {universities[0].id}")
    if universities:
        sources = session.scalars(
            select(DataSource).where(
                DataSource.university_id == universities[0].id,
                DataSource.source_type == "admission_xml",
                DataSource.source_url == ADMISSION_XML_URL,
            )
        ).all()
        if len(sources) != 1:
            conflicts.append(f"expected exactly one canonical BSEU XML source, got {len(sources)}")
    if conflicts:
        raise CatalogConflictError(conflicts)
    return universities[0]


def _program_matches(record: ProgramRecord, existing: Program) -> list[str]:
    expected = {
        "code": record.code,
        "slug": record.slug,
        "name": record.name,
        "faculty_name": record.faculty_name,
        "official_url": record.official_url,
        "active": True,
    }
    conflicts = [
        f"Program {record.match_key} has conflicting {field_name}"
        for field_name, value in expected.items()
        if getattr(existing, field_name) != value
    ]
    if _as_utc(existing.source_checked_at) != record.source_checked_at:
        conflicts.append(f"Program {record.match_key} has conflicting source_checked_at")
    return conflicts


def _offering_matches(record: OfferingRecord, existing: ProgramOffering) -> list[str]:
    expected = {
        "admission_year": record.admission_year,
        "study_form": record.study_form,
        "funding_type": record.funding_type,
        "places": record.places,
        "monitoring_supported": False,
        "monitoring_status": MonitoringStatus.REFERENCE_ONLY,
        "official_url": record.official_url,
        "source_url": record.source_url,
    }
    conflicts = [
        f"Offering {record.match_key} has conflicting {field_name}"
        for field_name, value in expected.items()
        if getattr(existing, field_name) != value
    ]
    if _as_utc(existing.source_checked_at) != record.source_checked_at:
        conflicts.append(f"Offering {record.match_key} has conflicting source_checked_at")
    return conflicts


def _economic_informatics_identity(
    session: Session,
    university: University,
    record: ProgramRecord,
) -> tuple[Program | None, ProgramOffering | None, list[str]]:
    by_slug = session.scalars(
        select(Program).where(Program.university_id == university.id, Program.slug == ECONOMIC_INFORMATICS_SLUG)
    ).all()
    by_code = session.scalars(
        select(Program).where(Program.university_id == university.id, Program.code == ECONOMIC_INFORMATICS_CODE)
    ).all()
    legacy_specialties = session.scalars(
        select(Specialty).where(
            Specialty.normalized_name == "экономическая информатика",
            Specialty.study_form == "дневная",
            Specialty.funding_type == "платная",
        )
    ).all()
    mapped = []
    if len(legacy_specialties) == 1:
        mapped = session.scalars(
            select(LegacySpecialtyMapping).where(LegacySpecialtyMapping.legacy_specialty_id == legacy_specialties[0].id)
        ).all()
    paid = session.scalars(
        select(ProgramOffering)
        .join(Program)
        .where(
            Program.university_id == university.id,
            ProgramOffering.admission_year == 2026,
            ProgramOffering.study_form == StudyForm.FULL_TIME,
            ProgramOffering.funding_type == FundingType.PAID,
        )
    ).all()
    sources = session.scalars(
        select(DataSource).where(
            DataSource.university_id == university.id,
            DataSource.source_url == ADMISSION_XML_URL,
        )
    ).all()

    any_existing = bool(by_slug or by_code)
    if not any_existing:
        collisions = [item for item in paid if item.program.name == ECONOMIC_INFORMATICS_NAME]
        if collisions or legacy_specialties or mapped:
            return None, None, ["Economic Informatics legacy/offering identity exists without canonical code and slug"]
        return None, None, []

    conflicts: list[str] = []
    if len(by_slug) != 1 or len(by_code) != 1 or by_slug[0].id != by_code[0].id:
        conflicts.append("Economic Informatics code and slug do not identify one canonical Program")
        return None, None, conflicts
    program = by_slug[0]
    if _normalized_name(program.name) != _normalized_name(record.name):
        conflicts.append("Economic Informatics canonical Program name conflicts with the audited identity")
    if len(legacy_specialties) != 1:
        conflicts.append(
            f"Economic Informatics legacy Specialty identity is ambiguous or missing ({len(legacy_specialties)})"
        )
    if len(mapped) != 1 or mapped[0].program_id != program.id:
        conflicts.append("Economic Informatics legacy mapping does not identify the canonical Program")
    program_paid = [item for item in paid if item.program_id == program.id]
    if len(program_paid) != 1:
        conflicts.append("Economic Informatics paid Offering identity is ambiguous or missing")
        paid_offering = None
    else:
        paid_offering = program_paid[0]
    if paid_offering is not None and (len(mapped) != 1 or mapped[0].program_offering_id != paid_offering.id):
        conflicts.append("Economic Informatics legacy mapping does not identify the paid Offering")
    if len(sources) != 1:
        conflicts.append("Economic Informatics BSEU XML source identity is ambiguous or missing")
    if paid_offering is not None:
        if paid_offering.places != 60:
            conflicts.append("Economic Informatics paid Offering conflicts with audited places=60")
        if not paid_offering.monitoring_supported or paid_offering.monitoring_status != MonitoringStatus.ONLINE:
            conflicts.append("Economic Informatics paid Offering no longer has the canonical online monitor identity")
    return program, paid_offering, conflicts


def _build_plan(session: Session, audit: BseuProgramAudit) -> _ImportPlan:
    university = _require_bseu(session)
    plan = _ImportPlan(audit=audit, university=university)
    existing_programs = session.scalars(select(Program).where(Program.university_id == university.id)).all()
    by_slug = {program.slug: program for program in existing_programs}
    by_normalized_name: dict[str, list[Program]] = defaultdict(list)
    for program in existing_programs:
        by_normalized_name[_normalized_name(program.name)].append(program)

    conflicts: list[str] = []
    for record in audit.programs:
        if record.code == ECONOMIC_INFORMATICS_CODE:
            existing, paid_offering, identity_conflicts = _economic_informatics_identity(session, university, record)
            conflicts.extend(identity_conflicts)
            if existing is None:
                plan.programs_to_create.append(record)
                plan.offerings_to_create.extend((record, offering) for offering in record.offerings)
            else:
                plan.programs_reused[record.match_key] = existing
                existing_offerings = {
                    (item.admission_year, item.study_form, item.funding_type): item for item in existing.offerings
                }
                for offering in record.offerings:
                    if offering.funding_type == FundingType.PAID and paid_offering is not None:
                        plan.offerings_reused[offering.match_key] = paid_offering
                    else:
                        business_key = (
                            offering.admission_year,
                            offering.study_form,
                            offering.funding_type,
                        )
                        existing_offering = existing_offerings.get(business_key)
                        if existing_offering is None:
                            plan.offerings_to_create.append((record, offering))
                        else:
                            conflicts.extend(_offering_matches(offering, existing_offering))
                            plan.offerings_reused[offering.match_key] = existing_offering
            continue

        existing = by_slug.get(record.slug)
        same_name = by_normalized_name.get(_normalized_name(record.name), [])
        if existing is None:
            if same_name:
                conflicts.append(
                    f"Program {record.match_key} has an existing display-name collision without its deterministic slug"
                )
            plan.programs_to_create.append(record)
            plan.offerings_to_create.extend((record, offering) for offering in record.offerings)
            continue
        if any(item.id != existing.id for item in same_name):
            conflicts.append(f"Program {record.match_key} has multiple existing normalized-name rows")
        conflicts.extend(_program_matches(record, existing))
        plan.programs_reused[record.match_key] = existing
        existing_offerings = {
            (item.admission_year, item.study_form, item.funding_type): item for item in existing.offerings
        }
        for offering in record.offerings:
            business_key = (offering.admission_year, offering.study_form, offering.funding_type)
            existing_offering = existing_offerings.get(business_key)
            if existing_offering is None:
                plan.offerings_to_create.append((record, offering))
            else:
                conflicts.extend(_offering_matches(offering, existing_offering))
                plan.offerings_reused[offering.match_key] = existing_offering

    if conflicts:
        raise CatalogConflictError(sorted(set(conflicts)))
    return plan


def _new_program(university_id: int, record: ProgramRecord) -> Program:
    return Program(
        university_id=university_id,
        code=record.code,
        slug=record.slug,
        name=record.name,
        qualification=None,
        faculty_name=record.faculty_name,
        education_level=None,
        duration_years=None,
        description=None,
        admission_subjects_json=None,
        career_fields_json=None,
        category_tags_json=None,
        official_url=record.official_url,
        active=True,
        source_checked_at=record.source_checked_at,
        verified_at=None,
    )


def _new_offering(program_id: int, record: OfferingRecord) -> ProgramOffering:
    return ProgramOffering(
        program_id=program_id,
        admission_year=record.admission_year,
        study_form=record.study_form,
        funding_type=record.funding_type,
        places=record.places,
        application_deadline=None,
        monitoring_supported=False,
        monitoring_status=MonitoringStatus.REFERENCE_ONLY,
        official_url=record.official_url,
        source_url=record.source_url,
        source_checked_at=record.source_checked_at,
        verified_at=None,
    )


def _add_offering(session: Session, offering: ProgramOffering) -> None:
    session.add(offering)


def _apply_plan(session: Session, plan: _ImportPlan) -> None:
    programs_by_key = dict(plan.programs_reused)
    for record in plan.programs_to_create:
        program = _new_program(plan.university.id, record)
        session.add(program)
        programs_by_key[record.match_key] = program
    session.flush()
    for program_record, offering_record in plan.offerings_to_create:
        _add_offering(
            session,
            _new_offering(programs_by_key[program_record.match_key].id, offering_record),
        )
    session.flush()


def import_bseu_programs(
    session: Session,
    audit: BseuProgramAudit,
    *,
    apply: bool = False,
) -> BseuProgramImportSummary:
    plan = _build_plan(session, audit)
    if apply:
        _apply_plan(session, plan)
    return BseuProgramImportSummary(
        confirmed_candidates=audit.confirmed_candidates,
        needs_review_skipped=audit.needs_review_skipped,
        program_identities_expected=len(audit.programs),
        programs_created=len(plan.programs_to_create),
        programs_reused=len(plan.programs_reused),
        offerings_created=len(plan.offerings_to_create),
        offerings_reused=len(plan.offerings_reused),
        conflicts=0,
        writes_applied=apply,
    )


def _database_engine(database_path: Path, *, readonly: bool) -> Engine:
    resolved = database_path.resolve()
    if not resolved.is_file():
        raise CatalogValidationError(f"Database path must identify an existing SQLite file: {resolved}")
    if readonly:
        uri = f"file:{resolved.as_posix()}?mode=ro&immutable=1"

        def connect_readonly() -> sqlite3.Connection:
            return sqlite3.connect(uri, uri=True, check_same_thread=False)

        engine = create_engine("sqlite://", creator=connect_readonly)
    else:
        engine = create_engine(URL.create("sqlite", database=str(resolved)), connect_args={"timeout": 30})

    @event.listens_for(engine, "connect")
    def configure_sqlite(dbapi_connection, _connection_record):  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


def run_bseu_program_import(
    database_path: Path,
    *,
    apply: bool = False,
    audit_path: Path = AUDIT_PATH,
    schema_path: Path = AUDIT_SCHEMA_PATH,
) -> BseuProgramImportSummary:
    # Audit/schema validation intentionally happens before a database engine or write transaction exists.
    audit = load_bseu_program_audit(audit_path, schema_path)
    engine = _database_engine(database_path, readonly=not apply)
    try:
        ensure_schema_current(engine)
        factory = sessionmaker(bind=engine, expire_on_commit=False)
        if apply:
            with factory.begin() as session:
                return import_bseu_programs(session, audit, apply=True)
        with factory() as session:
            return import_bseu_programs(session, audit, apply=False)
    finally:
        engine.dispose()
