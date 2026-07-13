from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, sessionmaker

import app.catalog_audit_service as audit_module
import app.cli as cli_module
from app.catalog_audit_service import audit_catalog
from app.catalog_import_service import (
    CANONICAL_RESEARCH_PATH,
    CANONICAL_SCHEMA_PATH,
    UNIVERSITY_DOCUMENT_SCHEMA_PATH,
    CatalogConflictError,
    export_university_document,
    import_university_document,
    load_canonical_records,
    seed_universities,
)
from app.catalog_models import (
    DataSource,
    FundingType,
    InstitutionKind,
    LegacySpecialtyMapping,
    MonitoringStatus,
    OwnershipType,
    Program,
    ProgramOffering,
    SourceHealth,
    StudyForm,
    University,
    UniversityCategory,
    UniversityCategoryLink,
)
from app.json_validation import load_json_document, validate_json_document
from app.models import AdmissionSnapshot, HttpCacheState, NotificationLog, ScraperRun, Specialty
from scripts.validate_university_research import load_json, validate_research

CHECKED_AT = datetime(2026, 7, 12, 18, 14, 28, tzinfo=UTC)
XML_URL = "https://bseu.by/abiturient/xml/1.xml"


def _seed_bseu(session: Session) -> None:
    university = University(
        id=1,
        code="bseu",
        slug="bseu",
        short_name="БГЭУ",
        full_name="Белорусский государственный экономический университет",
        institution_kind=InstitutionKind.UNIVERSITY,
        ownership_type=OwnershipType.STATE,
        city="Минск",
        region="Минск",
        official_site_url="https://bseu.by/",
        admissions_url="https://bseu.by/abiturient/",
        monitoring_status=MonitoringStatus.ONLINE,
        active=True,
        source_url=(
            "https://edu.gov.by/urovni-obrazovaniya/vysshee-obrazovanie/"
            "zakazchikam-spetsialistov/uchrezhdeniya-vysshego-obrazovaniya/g-minsk/index.php"
        ),
        source_checked_at=CHECKED_AT,
        data_verified_at=None,
    )
    category = UniversityCategory(id=1, code="economic", label_ru="Экономика")
    session.add_all([university, category])
    session.flush()
    session.add(UniversityCategoryLink(university_id=1, category_id=1))

    program = Program(
        id=1,
        university_id=1,
        code="6-05-0311-05",
        slug="economic-informatics",
        name="Экономическая информатика",
        qualification="Экономист. Информатик",
        faculty_name="Факультет цифровой экономики",
        education_level="bachelor",
        official_url="https://bseu.by/russian/teaching/specialities.htm",
        active=True,
        source_checked_at=CHECKED_AT,
    )
    session.add(program)
    session.flush()
    offering = ProgramOffering(
        id=1,
        program_id=1,
        admission_year=2026,
        study_form=StudyForm.FULL_TIME,
        funding_type=FundingType.PAID,
        places=60,
        monitoring_supported=True,
        monitoring_status=MonitoringStatus.ONLINE,
        official_url="https://bseu.by/russian/abiturient/tsp2026.pdf",
        source_url="https://bseu.by/russian/abiturient/tsp2026.pdf",
        source_checked_at=CHECKED_AT,
    )
    source = DataSource(
        id=1,
        university_id=1,
        source_type="admission_xml",
        source_url=XML_URL,
        adapter_name="legacy_admission_scraper",
        refresh_interval_minutes=10,
        enabled=True,
        last_attempt_at=datetime(2026, 7, 13, 17, 52, 14, tzinfo=UTC),
        last_success_at=datetime(2026, 7, 13, 17, 52, 14, tzinfo=UTC),
        consecutive_failures=0,
        health_status=SourceHealth.HEALTHY,
        etag='W/"fixture"',
        last_modified="Mon, 13 Jul 2026 15:00:00 GMT",
    )
    specialty = Specialty(
        id=1,
        normalized_name="экономическая информатика",
        display_name="Экономическая информатика",
        study_form="дневная",
        funding_type="платная",
        source_url=XML_URL,
        active=True,
    )
    session.add_all([offering, source, specialty])
    session.flush()
    session.add(
        LegacySpecialtyMapping(
            legacy_specialty_id=1,
            program_id=1,
            program_offering_id=1,
            mapping_version=1,
            notes="test mapping",
        )
    )
    session.add(
        AdmissionSnapshot(
            id=1,
            specialty_id=1,
            fetched_at=datetime(2026, 7, 13, 17, 46, 40, tzinfo=UTC),
            source_updated_at=datetime(2026, 7, 13, 18, 0, tzinfo=UTC),
            admission_plan=60,
            applications_total=25,
            competition=25 / 60,
            estimated_cutoff_min=None,
            estimated_cutoff_max=None,
            user_score=276,
            estimated_user_position=1,
            user_status="Высокая вероятность",
            distribution_json=json.dumps({"270-279": 2}, ensure_ascii=False),
            raw_data_hash="a" * 64,
            program_offering_id=1,
        )
    )
    session.add(
        ScraperRun(
            id=1,
            started_at=datetime(2026, 7, 13, 17, 52, 13, tzinfo=UTC),
            finished_at=datetime(2026, 7, 13, 17, 52, 14, tzinfo=UTC),
            status="success",
            http_status=200,
            rows_found=77,
            content_hash="b" * 64,
            data_source_id=1,
        )
    )
    session.add(
        NotificationLog(
            id=1,
            fingerprint="c" * 64,
            sent_at=datetime(2026, 7, 13, 17, 52, 15, tzinfo=UTC),
            message="fixture notification",
        )
    )
    session.add(
        HttpCacheState(
            url=XML_URL,
            etag='W/"fixture"',
            last_modified="Mon, 13 Jul 2026 15:00:00 GMT",
            checked_at=datetime(2026, 7, 13, 17, 52, 14, tzinfo=UTC),
        )
    )


def _table_rows(session: Session, table: str) -> list[dict[str, object]]:
    return [dict(row) for row in session.execute(text(f"SELECT * FROM {table} ORDER BY 1")).mappings()]


def _write_document(path: Path, document: dict[str, object]) -> None:
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def test_canonical_research_passes_existing_and_import_validation() -> None:
    data = load_json(CANONICAL_RESEARCH_PATH)
    schema = load_json(CANONICAL_SCHEMA_PATH)
    assert validate_research(data, schema) == []

    records, review_count = load_canonical_records()
    assert len(records) == 47
    assert sum(record.ownership_type == OwnershipType.STATE for record in records) == 43
    assert sum(record.ownership_type == OwnershipType.PRIVATE for record in records) == 4
    assert len({record.city for record in records}) == 11
    assert [record.code for record in records if record.monitoring_status == MonitoringStatus.ONLINE] == [
        "bseu"
    ]
    assert review_count == 5


def test_empty_catalog_imports_only_47_confirmed_universities(test_engine_factory) -> None:
    engine = test_engine_factory()
    with Session(engine) as session, session.begin():
        summary = seed_universities(session)
        assert summary.created == 47
        assert session.scalar(select(func.count()).select_from(University)) == 47
        assert session.scalar(
            select(func.count()).select_from(University).where(University.ownership_type == OwnershipType.STATE)
        ) == 43
        assert session.scalar(
            select(func.count()).select_from(University).where(University.ownership_type == OwnershipType.PRIVATE)
        ) == 4
        assert session.scalar(select(func.count()).select_from(UniversityCategory)) == 15
        assert session.scalar(select(func.count()).select_from(UniversityCategoryLink)) == 64
        assert session.scalar(select(func.count()).select_from(DataSource)) == 127

        research = load_json_document(CANONICAL_RESEARCH_PATH)
        review_names = {item["name"] for item in research["review_items"]}
        catalog_names = set(session.scalars(select(University.full_name)).all())
        assert review_names.isdisjoint(catalog_names)


def test_seed_preserves_bseu_runtime_and_legacy_rows_and_is_idempotent(test_engine_factory) -> None:
    engine = test_engine_factory()
    with Session(engine) as session, session.begin():
        _seed_bseu(session)
        session.flush()
        legacy_before = {
            table: _table_rows(session, table)
            for table in ("specialties", "admission_snapshots", "scraper_runs", "notification_logs")
        }
        xml_before = _table_rows(session, "data_sources")[0]

        first = seed_universities(session)
        assert first.created == 46
        assert first.updated == 1
        assert first.categories_created == 14
        assert first.categories_updated == 1
        assert first.links_created == 63
        assert first.sources_created == 127
        assert first.review_items_skipped == 5

        bseu = session.scalar(select(University).where(University.code == "bseu"))
        assert bseu is not None and bseu.id == 1
        assert session.scalar(select(Program.id).where(Program.university_id == 1)) == 1
        assert session.scalar(select(ProgramOffering.id).where(ProgramOffering.program_id == 1)) == 1
        xml_source = session.scalar(select(DataSource).where(DataSource.id == 1))
        assert xml_source is not None and xml_source.adapter_name == "legacy_admission_scraper"
        assert _table_rows(session, "data_sources")[0] == xml_before
        assert session.scalar(select(func.count()).select_from(University)) == 47
        assert session.scalar(select(func.count()).select_from(DataSource)) == 128
        assert session.scalar(select(func.count()).select_from(Program)) == 1
        assert session.scalar(select(func.count()).select_from(ProgramOffering)) == 1

        second = seed_universities(session)
        assert second.created == 0
        assert second.updated == 0
        assert second.unchanged == 47
        assert second.categories_created == 0
        assert second.categories_updated == 0
        assert second.links_created == 0
        assert second.sources_created == 0
        assert session.scalar(select(func.count()).select_from(University)) == 47
        assert session.scalar(select(func.count()).select_from(UniversityCategory)) == 15
        assert session.scalar(select(func.count()).select_from(UniversityCategoryLink)) == 64
        assert session.scalar(select(func.count()).select_from(DataSource)) == 128
        for table, before in legacy_before.items():
            assert _table_rows(session, table) == before


def test_dry_run_returns_plan_without_database_writes(test_engine_factory) -> None:
    engine = test_engine_factory()
    with Session(engine) as session:
        summary = seed_universities(session, dry_run=True)
        assert summary.created == 47
        assert summary.categories_created == 15
        assert summary.links_created == 64
        assert summary.sources_created == 127
        assert session.scalar(select(func.count()).select_from(University)) == 0
        assert session.scalar(select(func.count()).select_from(UniversityCategory)) == 0
        assert session.scalar(select(func.count()).select_from(DataSource)) == 0


def test_single_import_updates_allowed_value_and_null_does_not_erase_it(
    test_engine_factory, tmp_path: Path
) -> None:
    engine = test_engine_factory()
    with Session(engine) as session, session.begin():
        seed_universities(session)
        original = session.scalar(select(University).where(University.code == "brsu"))
        assert original is not None
        original_id = original.id
        document = export_university_document(session, "brsu")

    later = CHECKED_AT + timedelta(days=1)
    later_iso = later.isoformat().replace("+00:00", "Z")
    new_url = "https://www.brsu.by/abi/verified-admissions"
    document["university"]["admissions_url"] = new_url
    document["university"]["source_checked_at"] = later_iso
    document["university"]["data_verified_at"] = later_iso
    document["provenance"]["source_checked_at"] = later_iso
    document["provenance"]["data_verified_at"] = later_iso
    for source in document["sources"]:
        source["source_checked_at"] = later_iso
        if source["source_type"] == "admissions":
            source["source_url"] = new_url
    update_path = tmp_path / "brsu-update.json"
    _write_document(update_path, document)

    with Session(engine) as session, session.begin():
        summary = import_university_document(session, update_path)
        assert summary.updated == 1
        updated = session.scalar(select(University).where(University.code == "brsu"))
        assert updated is not None and updated.id == original_id
        assert updated.admissions_url == new_url

    null_document = json.loads(json.dumps(document))
    even_later = later + timedelta(days=1)
    even_later_iso = even_later.isoformat().replace("+00:00", "Z")
    null_document["university"]["admissions_url"] = None
    null_document["university"]["source_checked_at"] = even_later_iso
    null_document["university"]["data_verified_at"] = even_later_iso
    null_document["provenance"]["source_checked_at"] = even_later_iso
    null_document["provenance"]["data_verified_at"] = even_later_iso
    null_document["sources"] = [
        source for source in null_document["sources"] if source["source_type"] != "admissions"
    ]
    for source in null_document["sources"]:
        source["source_checked_at"] = even_later_iso
    null_path = tmp_path / "brsu-null.json"
    _write_document(null_path, null_document)

    with Session(engine) as session, session.begin():
        import_university_document(session, null_path)
        updated = session.scalar(select(University).where(University.code == "brsu"))
        assert updated is not None and updated.id == original_id
        assert updated.admissions_url == new_url


def test_slug_conflict_rolls_back_complete_seed(test_engine_factory) -> None:
    engine = test_engine_factory()
    with Session(engine) as session, session.begin():
        session.add(
            University(
                code="brsu",
                slug="conflicting-slug",
                short_name="Conflict",
                full_name="Conflict",
                institution_kind=InstitutionKind.UNIVERSITY,
                ownership_type=OwnershipType.STATE,
                city="Брест",
                region="Брестская область",
                official_site_url="https://conflict.test/",
                monitoring_status=MonitoringStatus.NEEDS_REVIEW,
                active=True,
                source_url="https://conflict.test/registry",
                source_checked_at=CHECKED_AT,
            )
        )
    with Session(engine) as session:
        with pytest.raises(CatalogConflictError, match="already uses slug"):
            with session.begin():
                seed_universities(session)
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(University)) == 1
        assert session.scalar(select(func.count()).select_from(UniversityCategory)) == 0
        assert session.scalar(select(func.count()).select_from(DataSource)) == 0


def test_catalog_audit_passes_and_detects_required_error_classes(test_engine_factory, monkeypatch) -> None:
    engine = test_engine_factory()
    with Session(engine) as session, session.begin():
        _seed_bseu(session)
        seed_universities(session)
    with Session(engine) as session:
        clean = audit_catalog(session)
        assert clean.ok, clean.errors
        assert clean.summary.universities_total == 47
        assert clean.summary.ownership_totals == {"private": 4, "state": 43}
        assert clean.summary.cities_total == 11

    with Session(engine) as session, session.begin():
        brsu = session.scalar(select(University).where(University.code == "brsu"))
        assert brsu is not None
        brsu.full_name = "Conflicting canonical name"
        brsu.monitoring_status = MonitoringStatus.ONLINE
        brsu.data_verified_at = CHECKED_AT
        registry = session.scalar(
            select(DataSource).where(
                DataSource.university_id == brsu.id,
                DataSource.source_type == "official_registry",
            )
        )
        assert registry is not None
        session.delete(registry)
    monkeypatch.setattr(audit_module, "duplicate_values", lambda _session, _column: ["duplicate"])
    with Session(engine) as session:
        broken = audit_catalog(session)
        assert not broken.ok
        joined = "\n".join(broken.errors)
        assert "Duplicate university" in joined
        assert "missing official_registry" in joined
        assert "unsupported university is marked online" in joined
        assert "canonical field mismatch" in joined


def test_bseu_export_passes_schema_and_reimport_is_idempotent(test_engine_factory, tmp_path: Path) -> None:
    engine = test_engine_factory()
    with Session(engine) as session, session.begin():
        _seed_bseu(session)
        seed_universities(session)
        document = export_university_document(session, "bseu")
        schema = load_json_document(UNIVERSITY_DOCUMENT_SCHEMA_PATH)
        validate_json_document(document, schema)
        assert document["programs"][0]["id"] == 1
        assert document["programs"][0]["offerings"][0]["id"] == 1
        serialized = json.dumps(document, ensure_ascii=False).lower()
        for forbidden in ("telegram", "token", "etag", "last_modified", "error_message"):
            assert forbidden not in serialized
        export_path = tmp_path / "bseu-export.json"
        _write_document(export_path, document)

    with Session(engine) as session, session.begin():
        summary = import_university_document(session, export_path)
        assert summary.created == 0
        assert summary.updated == 0
        assert summary.unchanged == 1
        assert session.scalar(select(func.count()).select_from(University).where(University.code == "bseu")) == 1
        assert session.scalar(select(func.count()).select_from(Program)) == 1
        assert session.scalar(select(func.count()).select_from(ProgramOffering)) == 1


def test_bseu_ids_and_online_status_are_preserved(test_engine_factory) -> None:
    engine = test_engine_factory()
    with Session(engine) as session, session.begin():
        _seed_bseu(session)
        seed_universities(session)
        bseu = session.scalar(select(University).where(University.code == "bseu"))
        assert bseu is not None and bseu.id == 1
        assert bseu.monitoring_status == MonitoringStatus.ONLINE
        assert session.scalar(select(Program.id).where(Program.university_id == bseu.id)) == 1
        assert session.scalar(select(ProgramOffering.id).where(ProgramOffering.program_id == 1)) == 1
        assert session.scalar(
            select(DataSource.id).where(
                DataSource.university_id == bseu.id,
                DataSource.source_type == "admission_xml",
            )
        ) == 1


def test_repeated_seed_does_not_change_entity_counts(test_engine_factory) -> None:
    engine = test_engine_factory()
    with Session(engine) as session, session.begin():
        _seed_bseu(session)
        seed_universities(session)
        before = {
            model.__tablename__: session.scalar(select(func.count()).select_from(model))
            for model in (University, UniversityCategory, UniversityCategoryLink, DataSource, Program, ProgramOffering)
        }
        result = seed_universities(session)
        after = {
            model.__tablename__: session.scalar(select(func.count()).select_from(model))
            for model in (University, UniversityCategory, UniversityCategoryLink, DataSource, Program, ProgramOffering)
        }
        assert result.created == result.updated == result.links_created == result.sources_created == 0
        assert before == after


def test_category_and_source_upserts_are_unique_and_preserve_xml_state(test_engine_factory) -> None:
    engine = test_engine_factory()
    with Session(engine) as session, session.begin():
        _seed_bseu(session)
        xml_before = _table_rows(session, "data_sources")[0]
        seed_universities(session)
        seed_universities(session)
        assert session.scalar(select(func.count()).select_from(UniversityCategory)) == 15
        assert session.scalar(select(func.count()).select_from(UniversityCategoryLink)) == 64
        assert session.scalar(select(func.count()).select_from(DataSource)) == 128
        duplicate_links = session.execute(
            text(
                "SELECT university_id, category_id, COUNT(*) AS n "
                "FROM university_category_links GROUP BY university_id, category_id HAVING n > 1"
            )
        ).all()
        duplicate_sources = session.execute(
            text(
                "SELECT university_id, source_type, source_url, COUNT(*) AS n "
                "FROM data_sources GROUP BY university_id, source_type, source_url HAVING n > 1"
            )
        ).all()
        assert duplicate_links == []
        assert duplicate_sources == []
        assert _table_rows(session, "data_sources")[0] == xml_before


def test_newer_verified_value_is_not_overwritten_by_older_research(test_engine_factory) -> None:
    engine = test_engine_factory()
    with Session(engine) as session, session.begin():
        _seed_bseu(session)
        seed_universities(session)
        brsu = session.scalar(select(University).where(University.code == "brsu"))
        assert brsu is not None
        brsu.full_name = "Ручное проверенное название"
        brsu.data_verified_at = CHECKED_AT + timedelta(days=5)
        session.flush()
        result = seed_universities(session)
        assert result.protected_by_newer_verification == 1
        assert brsu.full_name == "Ручное проверенное название"


def test_seed_preserves_exact_legacy_hashes_and_timestamps(test_engine_factory) -> None:
    engine = test_engine_factory()
    with Session(engine) as session, session.begin():
        _seed_bseu(session)
        session.flush()
        before = {
            table: _table_rows(session, table)
            for table in ("specialties", "admission_snapshots", "scraper_runs", "notification_logs")
        }
        seed_universities(session)
        for table, expected in before.items():
            assert _table_rows(session, table) == expected


def test_cli_slug_conflict_returns_nonzero_and_rolls_back(
    test_engine_factory, tmp_path: Path, monkeypatch, capsys
) -> None:
    engine = test_engine_factory()
    with Session(engine) as session, session.begin():
        seed_universities(session)
        document = export_university_document(session, "brsu")
        document["university"]["slug"] = "conflicting-brsu-slug"
        conflict_path = tmp_path / "brsu-conflict.json"
        _write_document(conflict_path, document)
        count_before = session.scalar(select(func.count()).select_from(University))

    monkeypatch.setattr(cli_module, "init_db", lambda: None)
    monkeypatch.setattr(cli_module, "SessionLocal", sessionmaker(bind=engine, expire_on_commit=False))
    assert cli_module.main(["import-university", str(conflict_path)]) == 2
    captured = capsys.readouterr()
    assert '"status": "error"' in captured.err
    assert "already uses slug" in captured.err
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(University)) == count_before
