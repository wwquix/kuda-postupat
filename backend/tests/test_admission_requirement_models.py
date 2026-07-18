from __future__ import annotations

import json
import socket
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.admission_requirement_models import (
    AdmissionRequirementEvidenceLink,
    AdmissionRequirementSource,
    AdmissionRequirementSubjectGroup,
    AdmissionRequirementSubjectOption,
    AdmissionSubject,
    AssessmentKind,
    ProgramAdmissionRequirementSet,
    validate_subject_group_options,
)
from app.catalog_models import (
    FundingType,
    InstitutionKind,
    MonitoringStatus,
    OwnershipType,
    Program,
    ProgramOffering,
    StudyForm,
    University,
)
from app.models import Base

AUDIT_PATH = Path(__file__).resolve().parents[2] / "docs" / "data" / "bseu-admission-subjects-2026.json"

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
PATHWAY_LABELS = {
    "general_competition": "Общий конкурс",
    "targeted_training": "Целевая подготовка",
}


@pytest.fixture(autouse=True)
def block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("admission requirement tests must remain offline")

    monkeypatch.setattr(socket, "create_connection", refuse_network)
    monkeypatch.setattr(socket.socket, "connect", refuse_network)


def _catalog(session: Session) -> tuple[University, Program, ProgramOffering]:
    checked_at = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)
    university = University(
        code="test-university",
        slug="test-university",
        short_name="Тестовый вуз",
        full_name="Тестовый университет",
        institution_kind=InstitutionKind.UNIVERSITY,
        ownership_type=OwnershipType.STATE,
        official_site_url="https://example.edu/",
        admissions_url="https://example.edu/admission",
        monitoring_status=MonitoringStatus.REFERENCE_ONLY,
        source_url="https://example.edu/",
        source_checked_at=checked_at,
    )
    program = Program(
        university=university,
        code="TEST-01",
        slug="test-program",
        name="Тестовая программа",
        admission_subjects_json=None,
        official_url="https://example.edu/program",
        source_checked_at=checked_at,
    )
    offering = ProgramOffering(
        program=program,
        admission_year=2026,
        study_form=StudyForm.FULL_TIME,
        funding_type=FundingType.PAID,
        places=10,
        monitoring_supported=False,
        monitoring_status=MonitoringStatus.REFERENCE_ONLY,
        official_url="https://example.edu/program",
        source_url="https://example.edu/program",
        source_checked_at=checked_at,
    )
    session.add_all([university, program, offering])
    session.commit()
    return university, program, offering


def _requirement_set(session: Session, program: Program) -> ProgramAdmissionRequirementSet:
    requirement_set = ProgramAdmissionRequirementSet(
        program_id=program.id,
        stable_key="2026-full-time-standard",
        admission_year=2026,
        pathway_code="general_competition",
        pathway_label="Общий конкурс",
        study_form="full_time",
        education_basis="general_secondary",
        track_description="full",
        source_checked_at=datetime(2026, 7, 18, 12, 0, tzinfo=UTC),
    )
    session.add(requirement_set)
    session.commit()
    return requirement_set


def _source(session: Session, university: University) -> AdmissionRequirementSource:
    source = AdmissionRequirementSource(
        university_id=university.id,
        source_key="official-2026-order",
        official_url="https://example.edu/order.pdf",
        official_title="Порядок приема на 2026 год",
        publisher="Тестовый университет",
        source_type="official_regulation",
        admission_year=2026,
        checked_at=datetime(2026, 7, 18, 12, 0, tzinfo=UTC),
    )
    session.add(source)
    session.commit()
    return source


def _subject(session: Session, key: str, label: str) -> AdmissionSubject:
    subject = AdmissionSubject(normalized_key=key, official_label_ru=label)
    session.add(subject)
    session.commit()
    return subject


def _reject(session: Session, item: object) -> None:
    session.add(item)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_models_are_registered_without_changing_legacy_program_column() -> None:
    expected_tables = {
        "admission_subjects",
        "admission_requirement_sources",
        "program_admission_requirement_sets",
        "admission_requirement_subject_groups",
        "admission_requirement_subject_options",
        "admission_requirement_evidence_links",
    }
    assert expected_tables <= set(Base.metadata.tables)
    assert Base.metadata.tables["programs"].c.admission_subjects_json.nullable is True


@pytest.mark.parametrize(
    ("key", "label"),
    [("", "Математика"), ("   ", "Математика"), ("mathematics", ""), ("mathematics", "   ")],
)
def test_subjects_reject_blank_keys_and_labels(
    test_engine_factory: Callable[[], Engine], key: str, label: str
) -> None:
    with Session(test_engine_factory()) as session:
        _reject(session, AdmissionSubject(normalized_key=key, official_label_ru=label))


def test_subject_normalized_key_is_unique(test_engine_factory: Callable[[], Engine]) -> None:
    with Session(test_engine_factory()) as session:
        _subject(session, "mathematics", "Математика")
        _reject(session, AdmissionSubject(normalized_key="mathematics", official_label_ru="Другое"))


def test_evidence_source_identity_required_text_and_year_are_enforced(
    test_engine_factory: Callable[[], Engine],
) -> None:
    with Session(test_engine_factory()) as session:
        university, _, _ = _catalog(session)
        _source(session, university)
        base = {
            "university_id": university.id,
            "source_key": "another-source",
            "official_url": "https://example.edu/another",
            "official_title": "Другой источник",
            "publisher": "Тестовый университет",
            "source_type": "html",
            "admission_year": 2026,
            "checked_at": datetime.now(UTC),
        }
        duplicate = dict(base, source_key="official-2026-order")
        _reject(session, AdmissionRequirementSource(**duplicate))
        for field in ("source_key", "official_url", "official_title", "publisher", "source_type"):
            invalid = dict(base)
            invalid[field] = "   "
            _reject(session, AdmissionRequirementSource(**invalid))
        _reject(session, AdmissionRequirementSource(**dict(base, admission_year=1900)))


def test_requirement_business_key_and_year_are_enforced(
    test_engine_factory: Callable[[], Engine],
) -> None:
    with Session(test_engine_factory()) as session:
        _, program, _ = _catalog(session)
        _requirement_set(session, program)
        _reject(
            session,
            ProgramAdmissionRequirementSet(
                program_id=program.id,
                stable_key="2026-full-time-standard",
                admission_year=2026,
                pathway_code="other",
                pathway_label="Другое",
                source_checked_at=datetime.now(UTC),
            ),
        )
        for field in ("stable_key", "pathway_code", "pathway_label"):
            values = {
                "program_id": program.id,
                "stable_key": f"blank-{field}",
                "admission_year": 2026,
                "pathway_code": "general_competition",
                "pathway_label": "Общий конкурс",
                "source_checked_at": datetime.now(UTC),
            }
            values[field] = "   "
            _reject(session, ProgramAdmissionRequirementSet(**values))
        _reject(
            session,
            ProgramAdmissionRequirementSet(
                program_id=program.id,
                stable_key="invalid-year",
                admission_year=1900,
                pathway_code="general_competition",
                pathway_label="Общий конкурс",
                source_checked_at=datetime.now(UTC),
            ),
        )


def test_group_position_and_choose_count_constraints(test_engine_factory: Callable[[], Engine]) -> None:
    with Session(test_engine_factory()) as session:
        _, program, _ = _catalog(session)
        requirement_set = _requirement_set(session, program)
        session.add(
            AdmissionRequirementSubjectGroup(
                requirement_set_id=requirement_set.id,
                stable_key="language",
                position=1,
                choose_count=1,
                assessment_kind=AssessmentKind.EXTERNAL_STANDARDIZED,
            )
        )
        session.commit()
        _reject(
            session,
            AdmissionRequirementSubjectGroup(
                requirement_set_id=requirement_set.id,
                stable_key="profile",
                position=1,
                choose_count=1,
                assessment_kind=AssessmentKind.EXTERNAL_STANDARDIZED,
            ),
        )
        _reject(
            session,
            AdmissionRequirementSubjectGroup(
                requirement_set_id=requirement_set.id,
                stable_key="invalid-choice",
                position=2,
                choose_count=0,
                assessment_kind=AssessmentKind.OTHER,
            ),
        )
        _reject(
            session,
            AdmissionRequirementSubjectGroup(
                requirement_set_id=requirement_set.id,
                stable_key="invalid-position",
                position=0,
                choose_count=1,
                assessment_kind=AssessmentKind.OTHER,
            ),
        )


def test_subject_options_reject_duplicate_subjects_and_positions(
    test_engine_factory: Callable[[], Engine],
) -> None:
    with Session(test_engine_factory()) as session:
        _, program, _ = _catalog(session)
        requirement_set = _requirement_set(session, program)
        group = AdmissionRequirementSubjectGroup(
            requirement_set_id=requirement_set.id,
            stable_key="language",
            position=1,
            choose_count=1,
            assessment_kind=AssessmentKind.EXTERNAL_STANDARDIZED,
        )
        first = _subject(session, "belarusian_language", "Белорусский язык")
        second = _subject(session, "russian_language", "Русский язык")
        session.add(group)
        session.commit()
        session.add(
            AdmissionRequirementSubjectOption(
                subject_group_id=group.id,
                subject_id=first.id,
                position=1,
            )
        )
        session.commit()
        _reject(
            session,
            AdmissionRequirementSubjectOption(
                subject_group_id=group.id,
                subject_id=first.id,
                position=2,
            ),
        )
        _reject(
            session,
            AdmissionRequirementSubjectOption(
                subject_group_id=group.id,
                subject_id=second.id,
                position=1,
            ),
        )
        third = _subject(session, "foreign_language", "Иностранный язык")
        _reject(
            session,
            AdmissionRequirementSubjectOption(
                subject_group_id=group.id,
                subject_id=third.id,
                position=0,
            ),
        )


def test_evidence_links_reject_duplicates(test_engine_factory: Callable[[], Engine]) -> None:
    with Session(test_engine_factory()) as session:
        university, program, _ = _catalog(session)
        requirement_set = _requirement_set(session, program)
        source = _source(session, university)
        session.add(
            AdmissionRequirementEvidenceLink(
                requirement_set_id=requirement_set.id,
                source_id=source.id,
            )
        )
        session.commit()
        _reject(
            session,
            AdmissionRequirementEvidenceLink(
                requirement_set_id=requirement_set.id,
                source_id=source.id,
                locator="page 2",
            ),
        )


def test_deletion_is_restricted_upward_and_cascades_only_requirement_dependents(
    test_engine_factory: Callable[[], Engine],
) -> None:
    engine = test_engine_factory()
    with Session(engine) as session:
        university, program, offering = _catalog(session)
        requirement_set = _requirement_set(session, program)
        source = _source(session, university)
        subject = _subject(session, "mathematics", "Математика")
        group = AdmissionRequirementSubjectGroup(
            requirement_set_id=requirement_set.id,
            stable_key="profile",
            position=1,
            choose_count=1,
            assessment_kind=AssessmentKind.EXTERNAL_STANDARDIZED,
        )
        session.add(group)
        session.flush()
        session.add_all(
            [
                AdmissionRequirementSubjectOption(
                    subject_group_id=group.id,
                    subject_id=subject.id,
                    position=1,
                ),
                AdmissionRequirementEvidenceLink(
                    requirement_set_id=requirement_set.id,
                    source_id=source.id,
                ),
            ]
        )
        session.commit()

        for model, item_id in (
            (AdmissionSubject, subject.id),
            (AdmissionRequirementSource, source.id),
            (Program, program.id),
            (University, university.id),
        ):
            item = session.get(model, item_id)
            assert item is not None
            session.delete(item)
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()

        session.delete(session.get(ProgramAdmissionRequirementSet, requirement_set.id))
        session.commit()
        assert session.get(ProgramAdmissionRequirementSet, requirement_set.id) is None
        assert session.scalar(select(func.count()).select_from(AdmissionRequirementSubjectGroup)) == 0
        assert session.scalar(select(func.count()).select_from(AdmissionRequirementSubjectOption)) == 0
        assert session.scalar(select(func.count()).select_from(AdmissionRequirementEvidenceLink)) == 0
        assert session.get(AdmissionSubject, subject.id) is not None
        assert session.get(AdmissionRequirementSource, source.id) is not None
        assert session.get(Program, program.id) is not None
        assert session.get(ProgramOffering, offering.id) is not None


def test_choose_count_validation_helper() -> None:
    validate_subject_group_options(choose_count=1, option_count=2)
    validate_subject_group_options(choose_count=2, option_count=2)
    with pytest.raises(ValueError, match="positive"):
        validate_subject_group_options(choose_count=0, option_count=2)
    with pytest.raises(ValueError, match="at least one"):
        validate_subject_group_options(choose_count=1, option_count=0)
    with pytest.raises(ValueError, match="cannot exceed"):
        validate_subject_group_options(choose_count=3, option_count=2)


def _load_audit() -> dict[str, object]:
    return json.loads(AUDIT_PATH.read_text(encoding="utf-8"))


def _materialize_audit(session: Session, audit: dict[str, object]) -> None:
    checked_at = datetime.fromisoformat(str(audit["checked_at"]))
    source_documents = list(audit["sources"])  # type: ignore[arg-type]
    programs = list(audit["programs"])  # type: ignore[arg-type]
    definitions = {
        item["definition_id"]: item
        for item in audit["requirement_definitions"]  # type: ignore[union-attr]
    }
    subject_documents: dict[str, dict[str, object]] = {}
    for definition in definitions.values():
        for group in definition["subject_groups"]:
            for subject in group["allowed_subjects"]:
                previous = subject_documents.setdefault(subject["subject_key"], subject)
                assert previous == subject

    university = University(
        code=str(audit["university_code"]),
        slug="bseu-admission-subjects-test",
        short_name="БГЭУ",
        full_name="Белорусский государственный экономический университет",
        institution_kind=InstitutionKind.UNIVERSITY,
        ownership_type=OwnershipType.STATE,
        official_site_url="https://bseu.by/",
        admissions_url="https://bseu.by/russian/abiturient/",
        monitoring_status=MonitoringStatus.REFERENCE_ONLY,
        source_url=source_documents[0]["url"],
        source_checked_at=checked_at,
    )
    session.add(university)
    session.flush()

    subjects: dict[str, AdmissionSubject] = {}
    for key, document in sorted(subject_documents.items()):
        subject = AdmissionSubject(
            normalized_key=key,
            official_label_ru=document["official_label_ru"],
            official_label_be=document["official_label_be"],
        )
        session.add(subject)
        subjects[key] = subject

    sources: dict[str, AdmissionRequirementSource] = {}
    for document in source_documents:
        source = AdmissionRequirementSource(
            university_id=university.id,
            source_key=document["source_id"],
            official_url=document["url"],
            official_title=document["title"],
            publisher=document["publisher"],
            source_type=document["source_type"],
            admission_year=document["publication_or_admission_year"],
            checked_at=datetime.fromisoformat(document["checked_at"]),
            content_hash=document["content_sha256"],
            evidence_note=document["evidence_note"],
        )
        session.add(source)
        sources[document["source_id"]] = source
    session.flush()

    for program_document in programs:
        program = Program(
            university_id=university.id,
            code=program_document["existing_code"],
            slug=program_document["slug"],
            name=program_document["imported_program_name"],
            admission_subjects_json=None,
            official_url=source_documents[0]["url"],
            source_checked_at=checked_at,
            verified_at=checked_at,
        )
        session.add(program)
        session.flush()
        for set_document in program_document["requirement_sets"]:
            pathway_code = set_document["admission_pathway"]
            requirement_set = ProgramAdmissionRequirementSet(
                program_id=program.id,
                stable_key=set_document["requirement_set_id"],
                admission_year=set_document["admission_year"],
                pathway_code=pathway_code,
                pathway_label=PATHWAY_LABELS[pathway_code],
                study_form=set_document["study_form"],
                education_basis=set_document["education_basis"],
                track_description=set_document["track"],
                applicability_note=set_document["applicability"],
                source_checked_at=checked_at,
                verified_at=checked_at,
            )
            session.add(requirement_set)
            session.flush()
            definition = definitions[set_document["requirement_definition_id"]]
            for group_document in definition["subject_groups"]:
                options = group_document["allowed_subjects"]
                validate_subject_group_options(
                    choose_count=group_document["choose_count"],
                    option_count=len(options),
                )
                assessment_form = group_document["assessment_form"]
                group = AdmissionRequirementSubjectGroup(
                    requirement_set_id=requirement_set.id,
                    stable_key=group_document["group_key"],
                    position=group_document["position"],
                    choose_count=group_document["choose_count"],
                    assessment_kind=ASSESSMENT_KINDS[assessment_form],
                    official_assessment_label=ASSESSMENT_LABELS[assessment_form],
                    note=group_document["note"],
                )
                session.add(group)
                session.flush()
                for option_position, option_document in enumerate(options, start=1):
                    session.add(
                        AdmissionRequirementSubjectOption(
                            subject_group_id=group.id,
                            subject_id=subjects[option_document["subject_key"]].id,
                            position=option_position,
                        )
                    )
            for source_id in set_document["source_ids"]:
                source_document = next(item for item in source_documents if item["source_id"] == source_id)
                session.add(
                    AdmissionRequirementEvidenceLink(
                        requirement_set_id=requirement_set.id,
                        source_id=sources[source_id].id,
                        locator=source_document["relevant_reference"],
                        evidence_note=source_document["evidence_note"],
                    )
                )
    session.commit()


def test_full_audit_is_representable_without_flattening_or_legacy_json(
    test_engine_factory: Callable[[], Engine], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    configured_database = tmp_path / "must-not-open.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{configured_database.as_posix()}")
    audit = _load_audit()
    with Session(test_engine_factory()) as session:
        _materialize_audit(session, audit)

        assert session.scalar(select(func.count()).select_from(Program)) == 17
        assert session.scalar(select(func.count()).select_from(ProgramAdmissionRequirementSet)) == 37
        assert session.scalar(select(func.count()).select_from(AdmissionSubject)) == 11
        assert session.scalar(select(func.count()).select_from(AdmissionRequirementSource)) == 3
        populated_legacy_json = select(func.count()).select_from(Program).where(
            Program.admission_subjects_json.is_not(None)
        )
        assert session.scalar(populated_legacy_json) == 0

        requirement_sets = session.scalars(
            select(ProgramAdmissionRequirementSet).order_by(ProgramAdmissionRequirementSet.stable_key)
        ).all()
        assert {(item.pathway_code, item.track_description) for item in requirement_sets} >= {
            ("general_competition", "full"),
            ("general_competition", "shortened"),
            ("targeted_training", "full"),
        }
        assert {item.study_form for item in requirement_sets} == {"full_time", "part_time"}
        assert {group.assessment_kind for item in requirement_sets for group in item.subject_groups} == {
            AssessmentKind.EXTERNAL_STANDARDIZED,
            AssessmentKind.INTERNAL_WRITTEN_EXAMINATION,
            AssessmentKind.INTERNAL_ORAL_EXAMINATION,
        }
        assert {group.official_assessment_label for item in requirement_sets for group in item.subject_groups} == set(
            ASSESSMENT_LABELS.values()
        )

        definitions = {
            item["definition_id"]: item
            for item in audit["requirement_definitions"]  # type: ignore[union-attr]
        }
        expected_groups = []
        for program_document in audit["programs"]:  # type: ignore[union-attr]
            for set_document in program_document["requirement_sets"]:
                definition = definitions[set_document["requirement_definition_id"]]
                for group_document in definition["subject_groups"]:
                    expected_groups.append(
                        (
                            set_document["requirement_set_id"],
                            group_document["position"],
                            group_document["choose_count"],
                            tuple(item["subject_key"] for item in group_document["allowed_subjects"]),
                        )
                    )
        actual_groups = [
            (
                requirement_set.stable_key,
                group.position,
                group.choose_count,
                tuple(option.subject.normalized_key for option in group.subject_options),
            )
            for requirement_set in requirement_sets
            for group in requirement_set.subject_groups
        ]
        assert sorted(actual_groups) == sorted(expected_groups)
        expected_link_count = sum(
            len(set_document["source_ids"])
            for program_document in audit["programs"]  # type: ignore[union-attr]
            for set_document in program_document["requirement_sets"]
        )
        assert session.scalar(select(func.count()).select_from(AdmissionRequirementEvidenceLink)) == expected_link_count
        assert all(item.evidence_links for item in requirement_sets)

    assert not configured_database.exists()
