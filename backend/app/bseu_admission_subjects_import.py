from __future__ import annotations

import hashlib
import shutil
import sqlite3
import tempfile
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import URL, Engine, create_engine, event, inspect, select, text
from sqlalchemy.orm import Session, sessionmaker

from .admission_requirement_models import (
    AdmissionRequirementEvidenceLink,
    AdmissionRequirementSource,
    AdmissionRequirementSubjectGroup,
    AdmissionRequirementSubjectOption,
    AdmissionSubject,
    AssessmentKind,
    ProgramAdmissionRequirementSet,
    validate_subject_group_options,
)
from .catalog_import_service import CatalogConflictError, CatalogValidationError
from .catalog_models import Program, University
from .json_validation import JsonDocumentError, load_and_validate_json

ROOT_DIR = Path(__file__).resolve().parents[2]
AUDIT_PATH = ROOT_DIR / "docs" / "data" / "bseu-admission-subjects-2026.json"
AUDIT_SCHEMA_PATH = ROOT_DIR / "docs" / "data" / "bseu-admission-subjects-2026.schema.json"

BSEU_CODE = "bseu"
SUPPORTED_ADMISSION_YEAR = 2026
EXPECTED_PROGRAMS = 17
EXPECTED_REQUIREMENT_SETS = 37
EXPECTED_SUBJECTS = 11
EXPECTED_SOURCES = 3

PATHWAY_LABELS = {
    "general_competition": "Общий конкурс",
    "targeted_training": "Целевая подготовка",
}
STUDY_FORM_LABELS = {
    "full_time": "Очная (дневная) форма",
    "part_time": "Заочная форма",
}
ASSESSMENT_KINDS = {
    "ce_or_ct": AssessmentKind.EXTERNAL_STANDARDIZED,
    "internal_written": AssessmentKind.INTERNAL_WRITTEN_EXAMINATION,
    "internal_oral": AssessmentKind.INTERNAL_ORAL_EXAMINATION,
}
ASSESSMENT_LABELS = {
    "ce_or_ct": "ЦЭ/ЦТ",
    "internal_written": "Внутренний письменный экзамен",
    "internal_oral": "Внутренний устный экзамен",
}


@dataclass(frozen=True)
class ProgramIdentity:
    audit_identity: str
    slug: str
    existing_code: str | None
    imported_name: str


@dataclass(frozen=True)
class SubjectRecord:
    normalized_key: str
    official_label_ru: str
    official_label_be: str | None


@dataclass(frozen=True)
class SourceRecord:
    source_key: str
    official_url: str
    official_title: str
    publisher: str
    source_type: str
    publication_year: int | None
    admission_year: int | None
    checked_at: datetime
    content_hash: str | None
    evidence_note: str | None
    locator: str | None


@dataclass(frozen=True)
class RequirementSetRecord:
    program_slug: str
    stable_key: str
    admission_year: int
    pathway_code: str
    pathway_label: str
    study_form: str | None
    study_form_label: str | None
    funding_applicability: str | None
    education_basis: str | None
    track_description: str | None
    applicability_note: str | None
    active: bool
    source_checked_at: datetime
    verified_at: datetime | None


@dataclass(frozen=True)
class GroupRecord:
    program_slug: str
    requirement_set_key: str
    admission_year: int
    stable_key: str
    position: int
    choose_count: int
    assessment_kind: AssessmentKind
    official_assessment_label: str | None
    note: str | None


@dataclass(frozen=True)
class OptionRecord:
    program_slug: str
    requirement_set_key: str
    admission_year: int
    group_key: str
    position: int
    subject_key: str


@dataclass(frozen=True)
class EvidenceLinkRecord:
    program_slug: str
    requirement_set_key: str
    admission_year: int
    source_key: str
    locator: str | None
    evidence_note: str | None


@dataclass(frozen=True)
class BseuAdmissionAudit:
    path: Path
    sha256: str
    university_code: str
    admission_year: int
    checked_at: datetime
    programs: tuple[ProgramIdentity, ...]
    subjects: tuple[SubjectRecord, ...]
    sources: tuple[SourceRecord, ...]
    requirement_sets: tuple[RequirementSetRecord, ...]
    groups: tuple[GroupRecord, ...]
    options: tuple[OptionRecord, ...]
    evidence_links: tuple[EvidenceLinkRecord, ...]


@dataclass(frozen=True)
class PlannedRow:
    record: object
    create: bool


@dataclass(frozen=True)
class BseuAdmissionImportPlan:
    program_ids: tuple[tuple[str, int], ...]
    subjects: tuple[PlannedRow, ...]
    sources: tuple[PlannedRow, ...]
    requirement_sets: tuple[PlannedRow, ...]
    groups: tuple[PlannedRow, ...]
    options: tuple[PlannedRow, ...]
    evidence_links: tuple[PlannedRow, ...]


@dataclass(frozen=True)
class BseuAdmissionImportSummary:
    mode: Literal["dry-run", "apply"]
    database_path: str
    audit_path: str
    audit_sha256: str
    admission_year: int
    university: str
    programs_expected: int
    programs_matched: int
    subjects_created: int
    subjects_reused: int
    evidence_sources_created: int
    evidence_sources_reused: int
    requirement_sets_created: int
    requirement_sets_reused: int
    groups_created: int
    groups_reused: int
    subject_options_created: int
    subject_options_reused: int
    evidence_links_created: int
    evidence_links_reused: int
    unchanged_rows: int
    conflicts: int
    transaction_committed: bool

    def as_dict(self) -> dict[str, str | int | bool]:
        return {
            "mode": self.mode,
            "database_path": self.database_path,
            "audit_path": self.audit_path,
            "audit_sha256": self.audit_sha256,
            "admission_year": self.admission_year,
            "university": self.university,
            "programs_expected": self.programs_expected,
            "programs_matched": self.programs_matched,
            "subjects_created": self.subjects_created,
            "subjects_reused": self.subjects_reused,
            "evidence_sources_created": self.evidence_sources_created,
            "evidence_sources_reused": self.evidence_sources_reused,
            "requirement_sets_created": self.requirement_sets_created,
            "requirement_sets_reused": self.requirement_sets_reused,
            "groups_created": self.groups_created,
            "groups_reused": self.groups_reused,
            "subject_options_created": self.subject_options_created,
            "subject_options_reused": self.subject_options_reused,
            "evidence_links_created": self.evidence_links_created,
            "evidence_links_reused": self.evidence_links_reused,
            "unchanged_rows": self.unchanged_rows,
            "conflicts": self.conflicts,
            "transaction_committed": self.transaction_committed,
        }


def _parse_datetime(value: str, field_name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CatalogValidationError(f"Invalid {field_name}: {value!r}") from exc
    if parsed.tzinfo is None:
        raise CatalogValidationError(f"{field_name} must include a timezone")
    return parsed.astimezone(UTC)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _expected_slug(identity: str) -> str:
    if identity == "bseu|code|6-05-0311-05":
        return "economic-informatics"
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]
    return f"bseu-audit-{digest}"


def _audit_semantic_errors(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if data["university_code"] != BSEU_CODE:
        errors.append(f"university_code must be {BSEU_CODE!r}")
    if data["admission_year"] != SUPPORTED_ADMISSION_YEAR:
        errors.append(f"unsupported admission_year {data['admission_year']!r}")

    sources = data["sources"]
    definitions = data["requirement_definitions"]
    programs = data["programs"]
    source_ids = [item["source_id"] for item in sources]
    definition_ids = [item["definition_id"] for item in definitions]
    program_identities = [item["program_identity"] for item in programs]
    program_slugs = [item["slug"] for item in programs]
    errors.extend(f"duplicate source identity {key}" for key, count in Counter(source_ids).items() if count > 1)
    errors.extend(
        f"duplicate requirement definition identity {key}"
        for key, count in Counter(definition_ids).items()
        if count > 1
    )
    errors.extend(
        f"duplicate Program audit identity {key}" for key, count in Counter(program_identities).items() if count > 1
    )
    errors.extend(f"duplicate Program slug {key}" for key, count in Counter(program_slugs).items() if count > 1)

    known_sources = set(source_ids)
    known_definitions = set(definition_ids)
    subject_documents: dict[str, tuple[str, str | None]] = {}
    definition_by_id = {item["definition_id"]: item for item in definitions}
    for definition in definitions:
        if not set(definition["source_ids"]) <= known_sources:
            errors.append(f"{definition['definition_id']}: missing source reference")
        group_keys: list[str] = []
        positions: list[int] = []
        for group in definition["subject_groups"]:
            group_keys.append(group["group_key"])
            positions.append(group["position"])
            try:
                validate_subject_group_options(
                    choose_count=group["choose_count"], option_count=len(group["allowed_subjects"])
                )
            except ValueError as exc:
                errors.append(f"{definition['definition_id']}/{group['group_key']}: {exc}")
            for subject in group["allowed_subjects"]:
                semantic = (subject["official_label_ru"], subject["official_label_be"])
                previous = subject_documents.setdefault(subject["subject_key"], semantic)
                if previous != semantic:
                    errors.append(f"subject {subject['subject_key']} has inconsistent official labels")
        if len(group_keys) != len(set(group_keys)):
            errors.append(f"{definition['definition_id']}: duplicate group_key")
        if positions != list(range(1, len(positions) + 1)):
            errors.append(f"{definition['definition_id']}: group positions must be contiguous from 1")

    requirement_ids: list[str] = []
    for program in programs:
        identity = program["program_identity"]
        expected_identity = (
            f"bseu|code|{program['existing_code']}"
            if program["existing_code"] is not None
            else f"bseu|normalized-name|{' '.join(program['imported_program_name'].split()).casefold()}"
        )
        if identity != expected_identity or program["slug"] != _expected_slug(identity):
            errors.append(f"{identity}: malformed Program identity")
        if program["status"] != "confirmed" or program["review_reason"] is not None:
            errors.append(f"{identity}: only confirmed target Programs may be imported")
        if not set(program["source_ids"]) <= known_sources:
            errors.append(f"{identity}: missing Program source reference")
        for requirement_set in program["requirement_sets"]:
            requirement_ids.append(requirement_set["requirement_set_id"])
            if requirement_set["admission_year"] != data["admission_year"]:
                errors.append(f"{requirement_set['requirement_set_id']}: admission year mismatch")
            definition_id = requirement_set["requirement_definition_id"]
            if definition_id not in known_definitions:
                errors.append(f"{requirement_set['requirement_set_id']}: unknown requirement definition")
            if not set(requirement_set["source_ids"]) <= known_sources:
                errors.append(f"{requirement_set['requirement_set_id']}: missing source reference")
            if definition_id in definition_by_id and not set(definition_by_id[definition_id]["source_ids"]) <= set(
                requirement_set["source_ids"]
            ):
                errors.append(f"{requirement_set['requirement_set_id']}: incomplete definition evidence")
            study_form_label = STUDY_FORM_LABELS.get(requirement_set["study_form"])
            if study_form_label is None or not requirement_set["applicability"].startswith(study_form_label):
                errors.append(f"{requirement_set['requirement_set_id']}: inconsistent study-form applicability")
            if requirement_set["admission_pathway"] not in PATHWAY_LABELS:
                errors.append(f"{requirement_set['requirement_set_id']}: unsupported admission pathway")

    errors.extend(
        f"duplicate requirement-set identity {key}" for key, count in Counter(requirement_ids).items() if count > 1
    )
    summary = data["summary"]
    actual_summary = {
        "target_programs": len(programs),
        "confirmed": sum(item["status"] == "confirmed" for item in programs),
        "needs_review": sum(item["status"] == "needs_review" for item in programs),
        "unavailable": sum(item["status"] == "unavailable" for item in programs),
        "requirement_sets": len(requirement_ids),
        "requirement_definitions": len(definitions),
        "official_sources": len(sources),
    }
    if summary != actual_summary:
        errors.append("summary does not match the audited rows")
    if (
        len(programs),
        len(requirement_ids),
        len(subject_documents),
        len(sources),
    ) != (EXPECTED_PROGRAMS, EXPECTED_REQUIREMENT_SETS, EXPECTED_SUBJECTS, EXPECTED_SOURCES):
        errors.append("tracked scope must remain exactly 17 Programs, 37 sets, 11 subjects and 3 sources")
    if data["review_items"]:
        errors.append("canonical import audit must not contain unresolved review items")
    return errors


def load_bseu_admission_audit(
    audit_path: Path = AUDIT_PATH,
    schema_path: Path = AUDIT_SCHEMA_PATH,
) -> BseuAdmissionAudit:
    resolved = audit_path.resolve()
    try:
        raw = resolved.read_bytes()
    except OSError as exc:
        raise CatalogValidationError(f"Cannot read BSEU admission audit: {resolved}") from exc
    try:
        data = load_and_validate_json(resolved, schema_path)
    except JsonDocumentError as exc:
        raise CatalogValidationError(str(exc)) from exc
    if not isinstance(data, dict):
        raise CatalogValidationError("BSEU admission audit root must be an object")
    errors = _audit_semantic_errors(data)
    if errors:
        raise CatalogValidationError("; ".join(sorted(set(errors))))

    checked_at = _parse_datetime(data["checked_at"], "checked_at")
    sources = tuple(
        SourceRecord(
            source_key=item["source_id"],
            official_url=item["url"],
            official_title=item["title"],
            publisher=item["publisher"],
            source_type=item["source_type"],
            publication_year=None,
            admission_year=item["publication_or_admission_year"],
            checked_at=_parse_datetime(item["checked_at"], f"sources[{item['source_id']}].checked_at"),
            content_hash=item["content_sha256"],
            evidence_note=item["evidence_note"],
            locator=item["relevant_reference"],
        )
        for item in data["sources"]
    )
    source_by_key = {item.source_key: item for item in sources}
    definitions = {item["definition_id"]: item for item in data["requirement_definitions"]}
    subjects_by_key: dict[str, SubjectRecord] = {}
    programs: list[ProgramIdentity] = []
    requirement_sets: list[RequirementSetRecord] = []
    groups: list[GroupRecord] = []
    options: list[OptionRecord] = []
    links: list[EvidenceLinkRecord] = []
    for program_document in data["programs"]:
        program = ProgramIdentity(
            audit_identity=program_document["program_identity"],
            slug=program_document["slug"],
            existing_code=program_document["existing_code"],
            imported_name=program_document["imported_program_name"],
        )
        programs.append(program)
        for set_document in program_document["requirement_sets"]:
            requirement_sets.append(
                RequirementSetRecord(
                    program_slug=program.slug,
                    stable_key=set_document["requirement_set_id"],
                    admission_year=set_document["admission_year"],
                    pathway_code=set_document["admission_pathway"],
                    pathway_label=PATHWAY_LABELS[set_document["admission_pathway"]],
                    study_form=set_document["study_form"],
                    study_form_label=STUDY_FORM_LABELS[set_document["study_form"]],
                    funding_applicability=None,
                    education_basis=set_document["education_basis"],
                    track_description=set_document["track"],
                    applicability_note=set_document["applicability"],
                    active=True,
                    source_checked_at=checked_at,
                    verified_at=checked_at,
                )
            )
            definition = definitions[set_document["requirement_definition_id"]]
            for group_document in definition["subject_groups"]:
                group = GroupRecord(
                    program_slug=program.slug,
                    requirement_set_key=set_document["requirement_set_id"],
                    admission_year=set_document["admission_year"],
                    stable_key=group_document["group_key"],
                    position=group_document["position"],
                    choose_count=group_document["choose_count"],
                    assessment_kind=ASSESSMENT_KINDS[group_document["assessment_form"]],
                    official_assessment_label=ASSESSMENT_LABELS[group_document["assessment_form"]],
                    note=group_document["note"],
                )
                groups.append(group)
                for position, subject_document in enumerate(group_document["allowed_subjects"], start=1):
                    subject = SubjectRecord(
                        normalized_key=subject_document["subject_key"],
                        official_label_ru=subject_document["official_label_ru"],
                        official_label_be=subject_document["official_label_be"],
                    )
                    subjects_by_key.setdefault(subject.normalized_key, subject)
                    options.append(
                        OptionRecord(
                            program_slug=program.slug,
                            requirement_set_key=set_document["requirement_set_id"],
                            admission_year=set_document["admission_year"],
                            group_key=group.stable_key,
                            position=position,
                            subject_key=subject.normalized_key,
                        )
                    )
            for source_key in set_document["source_ids"]:
                source = source_by_key[source_key]
                links.append(
                    EvidenceLinkRecord(
                        program_slug=program.slug,
                        requirement_set_key=set_document["requirement_set_id"],
                        admission_year=set_document["admission_year"],
                        source_key=source_key,
                        locator=source.locator,
                        evidence_note=source.evidence_note,
                    )
                )
    return BseuAdmissionAudit(
        path=resolved,
        sha256=hashlib.sha256(raw).hexdigest(),
        university_code=data["university_code"],
        admission_year=data["admission_year"],
        checked_at=checked_at,
        programs=tuple(programs),
        subjects=tuple(sorted(subjects_by_key.values(), key=lambda item: item.normalized_key)),
        sources=sources,
        requirement_sets=tuple(requirement_sets),
        groups=tuple(groups),
        options=tuple(options),
        evidence_links=tuple(links),
    )


REQUIRED_MODELS = (
    AdmissionSubject,
    AdmissionRequirementSource,
    ProgramAdmissionRequirementSet,
    AdmissionRequirementSubjectGroup,
    AdmissionRequirementSubjectOption,
    AdmissionRequirementEvidenceLink,
)


def _verify_schema_prerequisites(session: Session) -> None:
    inspector = inspect(session.connection())
    existing_tables = set(inspector.get_table_names())
    errors: list[str] = []
    for model in REQUIRED_MODELS:
        table = model.__table__
        if table.name not in existing_tables:
            errors.append(f"missing table {table.name}")
            continue
        actual_columns = {column["name"] for column in inspector.get_columns(table.name)}
        missing_columns = set(table.columns.keys()) - actual_columns
        if missing_columns:
            errors.append(f"table {table.name} missing columns: {', '.join(sorted(missing_columns))}")
    if errors:
        raise CatalogValidationError("migration 0007 schema prerequisite failed: " + "; ".join(errors))
    if session.execute(text("PRAGMA foreign_keys")).scalar_one() != 1:
        raise CatalogValidationError("SQLite foreign keys must be enabled")


def _require_bseu_and_programs(
    session: Session, audit: BseuAdmissionAudit
) -> tuple[University, tuple[tuple[str, int], ...]]:
    by_code = session.scalars(select(University).where(University.code == BSEU_CODE)).all()
    by_slug = session.scalars(select(University).where(University.slug == BSEU_CODE)).all()
    conflicts: list[str] = []
    if len(by_code) != 1:
        conflicts.append(f"expected exactly one University with code bseu, got {len(by_code)}")
    if len(by_slug) != 1:
        conflicts.append(f"expected exactly one University with slug bseu, got {len(by_slug)}")
    if by_code and by_slug and by_code[0].id != by_slug[0].id:
        conflicts.append("BSEU code and slug identify different University rows")
    if conflicts:
        raise CatalogConflictError(conflicts)
    university = by_code[0]

    program_ids: list[tuple[str, int]] = []
    for identity in audit.programs:
        exact_slug = session.scalars(
            select(Program).where(Program.university_id == university.id, Program.slug == identity.slug)
        ).all()
        exact_name = session.scalars(
            select(Program).where(Program.university_id == university.id, Program.name == identity.imported_name)
        ).all()
        exact_code = (
            session.scalars(
                select(Program).where(Program.university_id == university.id, Program.code == identity.existing_code)
            ).all()
            if identity.existing_code is not None
            else []
        )
        if len(exact_slug) != 1:
            conflicts.append(f"Program {identity.audit_identity}: exact slug matched {len(exact_slug)} rows")
            continue
        program = exact_slug[0]
        if program.name != identity.imported_name:
            conflicts.append(f"Program {identity.audit_identity}: exact slug has a different name")
        if program.code != identity.existing_code:
            conflicts.append(f"Program {identity.audit_identity}: exact slug has a different existing code")
        if len(exact_name) != 1 or exact_name[0].id != program.id:
            conflicts.append(f"Program {identity.audit_identity}: exact imported name is missing or duplicated")
        if identity.existing_code is not None and (len(exact_code) != 1 or exact_code[0].id != program.id):
            conflicts.append(f"Program {identity.audit_identity}: exact existing code is missing or duplicated")
        program_ids.append((identity.slug, program.id))
    if conflicts:
        raise CatalogConflictError(sorted(set(conflicts)))
    return university, tuple(program_ids)


def _semantic_conflicts(label: str, existing: object, expected: dict[str, object]) -> list[str]:
    conflicts: list[str] = []
    for field_name, value in expected.items():
        actual = getattr(existing, field_name)
        if isinstance(value, datetime) or isinstance(actual, datetime):
            matches = _as_utc(actual) == _as_utc(value)  # type: ignore[arg-type]
        else:
            matches = actual == value
        if not matches:
            conflicts.append(f"{label} has conflicting {field_name}")
    return conflicts


def _build_plan(session: Session, audit: BseuAdmissionAudit) -> BseuAdmissionImportPlan:
    _verify_schema_prerequisites(session)
    university, program_ids = _require_bseu_and_programs(session, audit)
    program_id_by_slug = dict(program_ids)
    conflicts: list[str] = []

    subject_rows: list[PlannedRow] = []
    for record in audit.subjects:
        existing = session.scalars(
            select(AdmissionSubject).where(AdmissionSubject.normalized_key == record.normalized_key)
        ).all()
        if len(existing) > 1:
            conflicts.append(f"subject {record.normalized_key} matched multiple rows")
        if not existing:
            subject_rows.append(PlannedRow(record, True))
        else:
            conflicts.extend(
                _semantic_conflicts(
                    f"subject {record.normalized_key}",
                    existing[0],
                    {
                        "official_label_ru": record.official_label_ru,
                        "official_label_be": record.official_label_be,
                    },
                )
            )
            subject_rows.append(PlannedRow(record, False))

    source_rows: list[PlannedRow] = []
    source_ids: dict[str, int] = {}
    for record in audit.sources:
        existing = session.scalars(
            select(AdmissionRequirementSource).where(
                AdmissionRequirementSource.university_id == university.id,
                AdmissionRequirementSource.source_key == record.source_key,
            )
        ).all()
        if len(existing) > 1:
            conflicts.append(f"evidence source {record.source_key} matched multiple rows")
        if not existing:
            source_rows.append(PlannedRow(record, True))
        else:
            source = existing[0]
            source_ids[record.source_key] = source.id
            conflicts.extend(
                _semantic_conflicts(
                    f"evidence source {record.source_key}",
                    source,
                    {
                        "official_url": record.official_url,
                        "official_title": record.official_title,
                        "publisher": record.publisher,
                        "source_type": record.source_type,
                        "publication_year": record.publication_year,
                        "admission_year": record.admission_year,
                        "checked_at": record.checked_at,
                        "content_hash": record.content_hash,
                        "evidence_note": record.evidence_note,
                    },
                )
            )
            source_rows.append(PlannedRow(record, False))

    set_rows: list[PlannedRow] = []
    set_ids: dict[tuple[str, int, str], int] = {}
    for record in audit.requirement_sets:
        key = (record.program_slug, record.admission_year, record.stable_key)
        program_id = program_id_by_slug[record.program_slug]
        existing = session.scalars(
            select(ProgramAdmissionRequirementSet).where(
                ProgramAdmissionRequirementSet.program_id == program_id,
                ProgramAdmissionRequirementSet.admission_year == record.admission_year,
                ProgramAdmissionRequirementSet.stable_key == record.stable_key,
            )
        ).all()
        if len(existing) > 1:
            conflicts.append(f"requirement set {record.stable_key} matched multiple rows")
        if not existing:
            set_rows.append(PlannedRow(record, True))
        else:
            requirement_set = existing[0]
            set_ids[key] = requirement_set.id
            conflicts.extend(
                _semantic_conflicts(
                    f"requirement set {record.stable_key}",
                    requirement_set,
                    {
                        "pathway_code": record.pathway_code,
                        "pathway_label": record.pathway_label,
                        "study_form": record.study_form,
                        "study_form_label": record.study_form_label,
                        "funding_applicability": record.funding_applicability,
                        "education_basis": record.education_basis,
                        "track_description": record.track_description,
                        "applicability_note": record.applicability_note,
                        "active": record.active,
                        "source_checked_at": record.source_checked_at,
                        "verified_at": record.verified_at,
                    },
                )
            )
            set_rows.append(PlannedRow(record, False))

    group_rows: list[PlannedRow] = []
    group_ids: dict[tuple[str, int, str, str], int] = {}
    intended_groups_by_set: dict[tuple[str, int, str], set[str]] = {}
    for record in audit.groups:
        set_key = (record.program_slug, record.admission_year, record.requirement_set_key)
        intended_groups_by_set.setdefault(set_key, set()).add(record.stable_key)
        requirement_set_id = set_ids.get(set_key)
        if requirement_set_id is None:
            group_rows.append(PlannedRow(record, True))
            continue
        by_key = session.scalars(
            select(AdmissionRequirementSubjectGroup).where(
                AdmissionRequirementSubjectGroup.requirement_set_id == requirement_set_id,
                AdmissionRequirementSubjectGroup.stable_key == record.stable_key,
            )
        ).all()
        by_position = session.scalars(
            select(AdmissionRequirementSubjectGroup).where(
                AdmissionRequirementSubjectGroup.requirement_set_id == requirement_set_id,
                AdmissionRequirementSubjectGroup.position == record.position,
            )
        ).all()
        if not by_key and not by_position:
            group_rows.append(PlannedRow(record, True))
            continue
        if len(by_key) != 1 or len(by_position) != 1 or by_key[0].id != by_position[0].id:
            conflicts.append(f"group {record.requirement_set_key}/{record.stable_key} key/position conflict")
            group_rows.append(PlannedRow(record, False))
            continue
        group = by_key[0]
        group_ids[
            (record.program_slug, record.admission_year, record.requirement_set_key, record.stable_key)
        ] = group.id
        conflicts.extend(
            _semantic_conflicts(
                f"group {record.requirement_set_key}/{record.stable_key}",
                group,
                {
                    "position": record.position,
                    "choose_count": record.choose_count,
                    "assessment_kind": record.assessment_kind,
                    "official_assessment_label": record.official_assessment_label,
                    "note": record.note,
                },
            )
        )
        group_rows.append(PlannedRow(record, False))
    for set_key, expected_keys in intended_groups_by_set.items():
        requirement_set_id = set_ids.get(set_key)
        if requirement_set_id is None:
            continue
        existing_keys = set(
            session.scalars(
                select(AdmissionRequirementSubjectGroup.stable_key).where(
                    AdmissionRequirementSubjectGroup.requirement_set_id == requirement_set_id
                )
            ).all()
        )
        extra = existing_keys - expected_keys
        if extra:
            conflicts.append(f"requirement set {set_key[2]} has unexpected groups: {', '.join(sorted(extra))}")

    option_rows: list[PlannedRow] = []
    intended_options_by_group: dict[tuple[str, int, str, str], dict[int, str]] = {}
    for record in audit.options:
        group_key = (record.program_slug, record.admission_year, record.requirement_set_key, record.group_key)
        intended_options_by_group.setdefault(group_key, {})[record.position] = record.subject_key
        group_id = group_ids.get(group_key)
        if group_id is None:
            option_rows.append(PlannedRow(record, True))
            continue
        by_position = session.execute(
            select(AdmissionRequirementSubjectOption, AdmissionSubject.normalized_key)
            .join(AdmissionSubject, AdmissionSubject.id == AdmissionRequirementSubjectOption.subject_id)
            .where(
                AdmissionRequirementSubjectOption.subject_group_id == group_id,
                AdmissionRequirementSubjectOption.position == record.position,
            )
        ).all()
        by_subject = session.execute(
            select(AdmissionRequirementSubjectOption, AdmissionSubject.normalized_key)
            .join(AdmissionSubject, AdmissionSubject.id == AdmissionRequirementSubjectOption.subject_id)
            .where(
                AdmissionRequirementSubjectOption.subject_group_id == group_id,
                AdmissionSubject.normalized_key == record.subject_key,
            )
        ).all()
        if not by_position and not by_subject:
            option_rows.append(PlannedRow(record, True))
            continue
        if (
            len(by_position) != 1
            or len(by_subject) != 1
            or by_position[0][0].subject_id != by_subject[0][0].subject_id
            or by_position[0][1] != record.subject_key
        ):
            conflicts.append(
                f"option {record.requirement_set_key}/{record.group_key}/{record.position} has conflicting subject"
            )
        option_rows.append(PlannedRow(record, False))
    for group_key, expected in intended_options_by_group.items():
        group_id = group_ids.get(group_key)
        if group_id is None:
            continue
        actual = {
            position: subject_key
            for position, subject_key in session.execute(
                select(AdmissionRequirementSubjectOption.position, AdmissionSubject.normalized_key)
                .join(AdmissionSubject, AdmissionSubject.id == AdmissionRequirementSubjectOption.subject_id)
                .where(AdmissionRequirementSubjectOption.subject_group_id == group_id)
            ).all()
        }
        extra_positions = set(actual) - set(expected)
        if extra_positions:
            conflicts.append(
                f"group {group_key[2]}/{group_key[3]} has unexpected option positions: "
                + ", ".join(str(item) for item in sorted(extra_positions))
            )

    link_rows: list[PlannedRow] = []
    intended_links_by_set: dict[tuple[str, int, str], set[str]] = {}
    for record in audit.evidence_links:
        set_key = (record.program_slug, record.admission_year, record.requirement_set_key)
        intended_links_by_set.setdefault(set_key, set()).add(record.source_key)
        requirement_set_id = set_ids.get(set_key)
        source_id = source_ids.get(record.source_key)
        if requirement_set_id is None or source_id is None:
            link_rows.append(PlannedRow(record, True))
            continue
        existing = session.scalars(
            select(AdmissionRequirementEvidenceLink).where(
                AdmissionRequirementEvidenceLink.requirement_set_id == requirement_set_id,
                AdmissionRequirementEvidenceLink.source_id == source_id,
            )
        ).all()
        if not existing:
            link_rows.append(PlannedRow(record, True))
            continue
        if len(existing) != 1:
            conflicts.append(f"evidence link {record.requirement_set_key}/{record.source_key} matched multiple rows")
        conflicts.extend(
            _semantic_conflicts(
                f"evidence link {record.requirement_set_key}/{record.source_key}",
                existing[0],
                {"locator": record.locator, "evidence_note": record.evidence_note},
            )
        )
        link_rows.append(PlannedRow(record, False))
    for set_key, expected_sources in intended_links_by_set.items():
        requirement_set_id = set_ids.get(set_key)
        if requirement_set_id is None:
            continue
        actual_sources = set(
            session.scalars(
                select(AdmissionRequirementSource.source_key)
                .join(
                    AdmissionRequirementEvidenceLink,
                    AdmissionRequirementEvidenceLink.source_id == AdmissionRequirementSource.id,
                )
                .where(AdmissionRequirementEvidenceLink.requirement_set_id == requirement_set_id)
            ).all()
        )
        extra = actual_sources - expected_sources
        if extra:
            conflicts.append(f"requirement set {set_key[2]} has unexpected evidence links: {', '.join(sorted(extra))}")

    if conflicts:
        raise CatalogConflictError(sorted(set(conflicts)))
    return BseuAdmissionImportPlan(
        program_ids=program_ids,
        subjects=tuple(subject_rows),
        sources=tuple(source_rows),
        requirement_sets=tuple(set_rows),
        groups=tuple(group_rows),
        options=tuple(option_rows),
        evidence_links=tuple(link_rows),
    )


def _created(rows: tuple[PlannedRow, ...]) -> int:
    return sum(item.create for item in rows)


def _reused(rows: tuple[PlannedRow, ...]) -> int:
    return len(rows) - _created(rows)


def _summary(
    database_path: Path,
    audit: BseuAdmissionAudit,
    plan: BseuAdmissionImportPlan,
    *,
    mode: Literal["dry-run", "apply"],
    committed: bool,
) -> BseuAdmissionImportSummary:
    reused = sum(
        _reused(rows)
        for rows in (
            plan.subjects,
            plan.sources,
            plan.requirement_sets,
            plan.groups,
            plan.options,
            plan.evidence_links,
        )
    )
    return BseuAdmissionImportSummary(
        mode=mode,
        database_path=str(database_path.resolve()),
        audit_path=str(audit.path),
        audit_sha256=audit.sha256,
        admission_year=audit.admission_year,
        university=audit.university_code,
        programs_expected=len(audit.programs),
        programs_matched=len(plan.program_ids),
        subjects_created=_created(plan.subjects),
        subjects_reused=_reused(plan.subjects),
        evidence_sources_created=_created(plan.sources),
        evidence_sources_reused=_reused(plan.sources),
        requirement_sets_created=_created(plan.requirement_sets),
        requirement_sets_reused=_reused(plan.requirement_sets),
        groups_created=_created(plan.groups),
        groups_reused=_reused(plan.groups),
        subject_options_created=_created(plan.options),
        subject_options_reused=_reused(plan.options),
        evidence_links_created=_created(plan.evidence_links),
        evidence_links_reused=_reused(plan.evidence_links),
        unchanged_rows=reused,
        conflicts=0,
        transaction_committed=committed,
    )


def _database_engine(database_path: Path, *, readonly: bool) -> Engine:
    resolved = database_path.resolve()
    if not resolved.is_file():
        raise CatalogValidationError(f"Database path must identify an existing SQLite file: {resolved}")
    if readonly:
        snapshot_dir = Path(tempfile.mkdtemp(prefix="bseu-admission-subjects-dry-run-"))
        snapshot = snapshot_dir / resolved.name
        wal_source = resolved.with_name(f"{resolved.name}-wal")
        try:
            shutil.copyfile(resolved, snapshot)
            if wal_source.exists():
                shutil.copyfile(wal_source, snapshot.with_name(f"{snapshot.name}-wal"))
        except OSError:
            shutil.rmtree(snapshot_dir, ignore_errors=True)
            raise
        uri = f"file:{snapshot.as_posix()}?mode=ro"

        def connect_readonly() -> sqlite3.Connection:
            return sqlite3.connect(uri, uri=True, check_same_thread=False, timeout=30)

        engine = create_engine("sqlite://", creator=connect_readonly)

        @event.listens_for(engine, "engine_disposed")
        def remove_snapshot(_engine):  # type: ignore[no-untyped-def]
            shutil.rmtree(snapshot_dir, ignore_errors=True)
    else:
        engine = create_engine(URL.create("sqlite", database=str(resolved)), connect_args={"timeout": 30})

    @event.listens_for(engine, "connect")
    def configure_sqlite(dbapi_connection, _connection_record):  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        if readonly:
            cursor.execute("PRAGMA query_only=ON")
        cursor.close()

    if not readonly:

        @event.listens_for(engine, "begin")
        def begin_immediate(connection):  # type: ignore[no-untyped-def]
            connection.exec_driver_sql("BEGIN IMMEDIATE")

    return engine


def _apply_plan(session: Session, plan: BseuAdmissionImportPlan) -> None:
    for item in plan.subjects:
        if item.create:
            record = item.record
            assert isinstance(record, SubjectRecord)
            session.add(
                AdmissionSubject(
                    normalized_key=record.normalized_key,
                    official_label_ru=record.official_label_ru,
                    official_label_be=record.official_label_be,
                )
            )
    session.flush()
    subject_ids = dict(
        session.execute(
            select(AdmissionSubject.normalized_key, AdmissionSubject.id).where(
                AdmissionSubject.normalized_key.in_(
                    [item.record.normalized_key for item in plan.subjects if isinstance(item.record, SubjectRecord)]
                )
            )
        ).all()
    )

    university_id = session.scalar(select(University.id).where(University.code == BSEU_CODE))
    assert university_id is not None
    for item in plan.sources:
        if item.create:
            record = item.record
            assert isinstance(record, SourceRecord)
            session.add(
                AdmissionRequirementSource(
                    university_id=university_id,
                    source_key=record.source_key,
                    official_url=record.official_url,
                    official_title=record.official_title,
                    publisher=record.publisher,
                    source_type=record.source_type,
                    publication_year=record.publication_year,
                    admission_year=record.admission_year,
                    checked_at=record.checked_at,
                    content_hash=record.content_hash,
                    evidence_note=record.evidence_note,
                )
            )
    session.flush()
    source_ids = dict(
        session.execute(
            select(AdmissionRequirementSource.source_key, AdmissionRequirementSource.id).where(
                AdmissionRequirementSource.university_id == university_id,
                AdmissionRequirementSource.source_key.in_(
                    [item.record.source_key for item in plan.sources if isinstance(item.record, SourceRecord)]
                ),
            )
        ).all()
    )

    program_ids = dict(plan.program_ids)
    for item in plan.requirement_sets:
        if item.create:
            record = item.record
            assert isinstance(record, RequirementSetRecord)
            session.add(
                ProgramAdmissionRequirementSet(
                    program_id=program_ids[record.program_slug],
                    stable_key=record.stable_key,
                    admission_year=record.admission_year,
                    pathway_code=record.pathway_code,
                    pathway_label=record.pathway_label,
                    study_form=record.study_form,
                    study_form_label=record.study_form_label,
                    funding_applicability=record.funding_applicability,
                    education_basis=record.education_basis,
                    track_description=record.track_description,
                    applicability_note=record.applicability_note,
                    active=record.active,
                    source_checked_at=record.source_checked_at,
                    verified_at=record.verified_at,
                )
            )
    session.flush()
    set_ids: dict[tuple[str, int, str], int] = {}
    for item in plan.requirement_sets:
        record = item.record
        assert isinstance(record, RequirementSetRecord)
        set_id = session.scalar(
            select(ProgramAdmissionRequirementSet.id).where(
                ProgramAdmissionRequirementSet.program_id == program_ids[record.program_slug],
                ProgramAdmissionRequirementSet.admission_year == record.admission_year,
                ProgramAdmissionRequirementSet.stable_key == record.stable_key,
            )
        )
        assert set_id is not None
        set_ids[(record.program_slug, record.admission_year, record.stable_key)] = set_id

    for item in plan.groups:
        if item.create:
            record = item.record
            assert isinstance(record, GroupRecord)
            session.add(
                AdmissionRequirementSubjectGroup(
                    requirement_set_id=set_ids[
                        (record.program_slug, record.admission_year, record.requirement_set_key)
                    ],
                    stable_key=record.stable_key,
                    position=record.position,
                    choose_count=record.choose_count,
                    assessment_kind=record.assessment_kind,
                    official_assessment_label=record.official_assessment_label,
                    note=record.note,
                )
            )
    session.flush()
    group_ids: dict[tuple[str, int, str, str], int] = {}
    for item in plan.groups:
        record = item.record
        assert isinstance(record, GroupRecord)
        group_id = session.scalar(
            select(AdmissionRequirementSubjectGroup.id).where(
                AdmissionRequirementSubjectGroup.requirement_set_id
                == set_ids[(record.program_slug, record.admission_year, record.requirement_set_key)],
                AdmissionRequirementSubjectGroup.stable_key == record.stable_key,
            )
        )
        assert group_id is not None
        group_ids[(record.program_slug, record.admission_year, record.requirement_set_key, record.stable_key)] = (
            group_id
        )

    for item in plan.options:
        if item.create:
            record = item.record
            assert isinstance(record, OptionRecord)
            session.add(
                AdmissionRequirementSubjectOption(
                    subject_group_id=group_ids[
                        (
                            record.program_slug,
                            record.admission_year,
                            record.requirement_set_key,
                            record.group_key,
                        )
                    ],
                    subject_id=subject_ids[record.subject_key],
                    position=record.position,
                )
            )
    for item in plan.evidence_links:
        if item.create:
            record = item.record
            assert isinstance(record, EvidenceLinkRecord)
            session.add(
                AdmissionRequirementEvidenceLink(
                    requirement_set_id=set_ids[
                        (record.program_slug, record.admission_year, record.requirement_set_key)
                    ],
                    source_id=source_ids[record.source_key],
                    locator=record.locator,
                    evidence_note=record.evidence_note,
                )
            )
    session.flush()


def _verify_before_commit(session: Session, audit: BseuAdmissionAudit, plan: BseuAdmissionImportPlan) -> None:
    program_ids = dict(plan.program_ids)
    set_ids = {
        (record.program_slug, record.admission_year, record.stable_key): session.scalar(
            select(ProgramAdmissionRequirementSet.id).where(
                ProgramAdmissionRequirementSet.program_id == program_ids[record.program_slug],
                ProgramAdmissionRequirementSet.admission_year == record.admission_year,
                ProgramAdmissionRequirementSet.stable_key == record.stable_key,
            )
        )
        for record in audit.requirement_sets
    }
    for group in audit.groups:
        requirement_set_id = set_ids[(group.program_slug, group.admission_year, group.requirement_set_key)]
        assert requirement_set_id is not None
        group_id = session.scalar(
            select(AdmissionRequirementSubjectGroup.id).where(
                AdmissionRequirementSubjectGroup.requirement_set_id == requirement_set_id,
                AdmissionRequirementSubjectGroup.stable_key == group.stable_key,
            )
        )
        assert group_id is not None
        option_count = session.scalar(
            select(text("count(*)")).select_from(AdmissionRequirementSubjectOption).where(
                AdmissionRequirementSubjectOption.subject_group_id == group_id
            )
        )
        assert option_count is not None
        validate_subject_group_options(choose_count=group.choose_count, option_count=option_count)
    foreign_key_errors = session.execute(text("PRAGMA foreign_key_check")).all()
    if foreign_key_errors:
        raise CatalogValidationError(f"foreign-key check failed: {foreign_key_errors}")


def _verify_applied(database_path: Path, audit: BseuAdmissionAudit) -> None:
    engine = _database_engine(database_path, readonly=True)
    try:
        factory = sessionmaker(bind=engine, expire_on_commit=False)
        with factory() as session:
            plan = _build_plan(session, audit)
            if any(
                _created(rows)
                for rows in (
                    plan.subjects,
                    plan.sources,
                    plan.requirement_sets,
                    plan.groups,
                    plan.options,
                    plan.evidence_links,
                )
            ):
                raise CatalogValidationError("post-apply verification found missing imported rows")
            pathway_pairs = set(
                session.execute(
                    select(
                        ProgramAdmissionRequirementSet.pathway_code,
                        ProgramAdmissionRequirementSet.track_description,
                    ).where(
                        ProgramAdmissionRequirementSet.program_id.in_(dict(plan.program_ids).values()),
                        ProgramAdmissionRequirementSet.admission_year == audit.admission_year,
                    )
                ).all()
            )
            required_pairs = {
                ("general_competition", "full"),
                ("general_competition", "shortened"),
                ("targeted_training", "full"),
            }
            if not required_pairs <= pathway_pairs:
                raise CatalogValidationError("post-apply verification flattened distinct admission pathways")
            if session.execute(text("PRAGMA foreign_key_check")).all():
                raise CatalogValidationError("post-apply foreign-key check failed")
    finally:
        engine.dispose()


def run_bseu_admission_subjects_import(
    database_path: Path,
    *,
    mode: Literal["dry-run", "apply"],
    audit_path: Path = AUDIT_PATH,
    schema_path: Path = AUDIT_SCHEMA_PATH,
) -> BseuAdmissionImportSummary:
    if mode not in {"dry-run", "apply"}:
        raise CatalogValidationError("mode must be exactly 'dry-run' or 'apply'")
    # Strict audit validation intentionally completes before the database is opened.
    audit = load_bseu_admission_audit(audit_path, schema_path)
    engine = _database_engine(database_path, readonly=mode == "dry-run")
    try:
        factory = sessionmaker(bind=engine, expire_on_commit=False)
        if mode == "dry-run":
            with factory() as session:
                if session.execute(text("PRAGMA query_only")).scalar_one() != 1:
                    raise CatalogValidationError("SQLite dry-run connection must be query-only")
                plan = _build_plan(session, audit)
                return _summary(database_path, audit, plan, mode=mode, committed=False)

        with factory.begin() as session:
            plan = _build_plan(session, audit)
            _apply_plan(session, plan)
            _verify_before_commit(session, audit, plan)
        _verify_applied(database_path, audit)
        return _summary(database_path, audit, plan, mode=mode, committed=True)
    finally:
        engine.dispose()
