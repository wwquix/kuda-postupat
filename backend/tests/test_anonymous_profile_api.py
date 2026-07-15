from __future__ import annotations

import json
import socket
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.calculations import calculate_metrics
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
)
from app.database import get_db
from app.models import AdmissionSnapshot, Specialty
from app.profile_api import router
from app.profile_models import AnonymousProfile, SavedProgram, SavedUniversity
from app.profile_security import hash_profile_token


@pytest.fixture
def profile_api(
    tmp_path: Path,
    test_engine_factory: Callable[[str], Engine],
) -> tuple[TestClient, sessionmaker[Session], dict[str, int]]:
    database = tmp_path / "anonymous-profile.db"
    engine = test_engine_factory(f"sqlite:///{database.as_posix()}")
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    now = datetime.now(UTC)

    with session_factory() as session:
        alpha = University(
            code="alpha",
            slug="alpha",
            short_name="Альфа",
            full_name="Альфа университет",
            institution_kind=InstitutionKind.UNIVERSITY,
            ownership_type=OwnershipType.STATE,
            city="Брест",
            region="Брестская область",
            official_site_url="https://alpha.test",
            monitoring_status=MonitoringStatus.REFERENCE_ONLY,
            source_url="https://alpha.test/source",
            source_checked_at=now,
        )
        bseu = University(
            code="bseu",
            slug="bseu",
            short_name="БГЭУ",
            full_name="Белорусский государственный экономический университет",
            institution_kind=InstitutionKind.UNIVERSITY,
            ownership_type=OwnershipType.STATE,
            city="Минск",
            region="Минск",
            official_site_url="https://bseu.by",
            monitoring_status=MonitoringStatus.ONLINE,
            source_url="https://edu.gov.by/registry",
            source_checked_at=now,
        )
        session.add_all([alpha, bseu])
        session.flush()
        alpha_program = Program(
            university=alpha,
            slug="accounting",
            name="Бухгалтерский учёт",
            official_url="https://alpha.test/accounting",
            source_checked_at=now,
        )
        bseu_program = Program(
            university=bseu,
            code="6-05-0311-05",
            slug="economic-informatics",
            name="Экономическая информатика",
            official_url="https://bseu.by/economic-informatics",
            source_checked_at=now,
        )
        session.add_all([alpha_program, bseu_program])
        session.flush()
        offering = ProgramOffering(
            program=bseu_program,
            admission_year=2026,
            study_form=StudyForm.FULL_TIME,
            funding_type=FundingType.PAID,
            places=3,
            monitoring_supported=True,
            monitoring_status=MonitoringStatus.ONLINE,
            official_url="https://bseu.by/offering",
            source_url="https://bseu.by/offering",
            source_checked_at=now,
        )
        specialty = Specialty(
            normalized_name="экономическая информатика",
            display_name="Экономическая информатика",
            study_form="дневная",
            funding_type="платная",
            source_url="https://bseu.by/abiturient/xml/1.xml",
            active=True,
        )
        source = DataSource(
            university=bseu,
            source_type="admission_xml",
            source_url="https://bseu.by/abiturient/xml/1.xml",
            adapter_name="legacy_admission_scraper",
            enabled=True,
            last_attempt_at=now,
            last_success_at=now,
            health_status=SourceHealth.HEALTHY,
        )
        session.add_all([offering, specialty, source])
        session.flush()
        session.add(
            LegacySpecialtyMapping(
                legacy_specialty_id=specialty.id,
                program_id=bseu_program.id,
                program_offering_id=offering.id,
                mapping_version=1,
            )
        )
        distribution = {"300-309": 1, "290-299": 2, "280-289": 2}
        session.add(
            AdmissionSnapshot(
                specialty_id=specialty.id,
                program_offering_id=offering.id,
                fetched_at=now,
                source_updated_at=None,
                admission_plan=3,
                applications_total=5,
                competition=1.67,
                estimated_cutoff_min=290,
                estimated_cutoff_max=299,
                user_score=276,
                estimated_user_position=6,
                user_status="Пока не проходит",
                distribution_json=json.dumps(distribution),
                raw_data_hash="a" * 64,
            )
        )
        session.commit()
        ids = {
            "alpha_university": alpha.id,
            "bseu_university": bseu.id,
            "alpha_program": alpha_program.id,
            "bseu_program": bseu_program.id,
        }

    def override_db() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = override_db
    return TestClient(app), session_factory, ids


def create_profile(client: TestClient) -> tuple[str, dict[str, str]]:
    response = client.post("/api/profile")
    assert response.status_code == 201
    token = response.json()["token"]
    return token, {"Authorization": f"Bearer {token}"}


def test_profile_creation_hashes_secure_token_and_exposes_no_internal_identity(
    profile_api: tuple[TestClient, sessionmaker[Session], dict[str, int]],
) -> None:
    client, session_factory, _ids = profile_api
    token, headers = create_profile(client)

    assert len(token) >= 43
    with session_factory() as session:
        profile = session.scalar(select(AnonymousProfile))
        assert profile is not None
        assert profile.token_hash == hash_profile_token(token)
        assert profile.token_hash != token
        assert token not in profile.token_hash
    current = client.get("/api/profile", headers=headers)
    assert current.status_code == 200
    assert set(current.json()) == {"personal_score", "created_at", "updated_at"}
    assert token not in current.text
    assert "token_hash" not in current.text
    assert "id" not in current.json()


def test_invalid_or_missing_profile_token_is_controlled(
    profile_api: tuple[TestClient, sessionmaker[Session], dict[str, int]],
) -> None:
    client, _session_factory, _ids = profile_api
    for headers in ({}, {"Authorization": "Bearer invalid-token"}, {"Authorization": "Basic x"}):
        response = client.get("/api/profile/saved", headers=headers)
        assert response.status_code == 401
        assert response.json() == {"detail": "Требуется действующий токен анонимного профиля"}
        assert response.headers["www-authenticate"] == "Bearer"


def test_score_validation_update_status_and_clear(
    profile_api: tuple[TestClient, sessionmaker[Session], dict[str, int]],
) -> None:
    client, _session_factory, _ids = profile_api
    _token, headers = create_profile(client)
    saved = client.put(
        "/api/profile/programs/bseu/economic-informatics", headers=headers
    )
    assert saved.status_code == 200
    assert saved.json()["programs"][0]["monitoring_state"] == "score_required"

    for invalid_score in (-1, 501):
        invalid = client.patch(
            "/api/profile/score", headers=headers, json={"score": invalid_score}
        )
        assert invalid.status_code == 422

    updated = client.patch("/api/profile/score", headers=headers, json={"score": 292})
    assert updated.status_code == 200
    payload = updated.json()
    assert payload["profile"]["personal_score"] == 292
    status_payload = payload["programs"][0]
    assert status_payload["monitoring_state"] == "available"
    expected = calculate_metrics(
        3, 5, {"300-309": 1, "290-299": 2, "280-289": 2}, 292
    )
    assert status_payload["monitoring"]["status"] == expected.status
    assert status_payload["monitoring"]["estimated_user_position"] == expected.estimated_user_position
    assert status_payload["monitoring"]["estimated_cutoff_min"] == expected.cutoff_min
    assert status_payload["monitoring"]["estimated_cutoff_max"] == expected.cutoff_max

    cleared = client.patch("/api/profile/score", headers=headers, json={"score": None})
    assert cleared.status_code == 200
    assert cleared.json()["profile"]["personal_score"] is None
    assert cleared.json()["programs"][0]["monitoring_state"] == "score_required"


def test_university_save_remove_and_duplicate_requests_are_idempotent(
    profile_api: tuple[TestClient, sessionmaker[Session], dict[str, int]],
) -> None:
    client, session_factory, ids = profile_api
    _token, headers = create_profile(client)
    before_catalog_count: int
    with session_factory() as session:
        before_catalog_count = session.scalar(select(func.count()).select_from(University)) or 0

    for _ in range(2):
        saved = client.put("/api/profile/universities/bseu", headers=headers)
        assert saved.status_code == 200
        assert [item["university"]["slug"] for item in saved.json()["universities"]] == ["bseu"]
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(SavedUniversity)) == 1
        assert session.get(University, ids["bseu_university"]) is not None

    for _ in range(2):
        removed = client.delete("/api/profile/universities/bseu", headers=headers)
        assert removed.status_code == 200
        assert removed.json()["universities"] == []
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(SavedUniversity)) == 0
        assert session.scalar(select(func.count()).select_from(University)) == before_catalog_count


def test_program_save_remove_and_unknown_targets(
    profile_api: tuple[TestClient, sessionmaker[Session], dict[str, int]],
) -> None:
    client, session_factory, _ids = profile_api
    _token, headers = create_profile(client)

    for _ in range(2):
        saved = client.put(
            "/api/profile/programs/bseu/economic-informatics", headers=headers
        )
        assert saved.status_code == 200
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(SavedProgram)) == 1

    for path in (
        "/api/profile/universities/unknown",
        "/api/profile/programs/unknown/economic-informatics",
        "/api/profile/programs/bseu/unknown",
    ):
        assert client.put(path, headers=headers).status_code == 404

    for _ in range(2):
        removed = client.delete(
            "/api/profile/programs/bseu/economic-informatics", headers=headers
        )
        assert removed.status_code == 200
        assert removed.json()["programs"] == []


def test_saved_list_is_deterministic_and_unsupported_monitoring_is_explicit(
    profile_api: tuple[TestClient, sessionmaker[Session], dict[str, int]],
) -> None:
    client, _session_factory, _ids = profile_api
    _token, headers = create_profile(client)
    client.put("/api/profile/universities/bseu", headers=headers)
    client.put("/api/profile/universities/alpha", headers=headers)
    client.put("/api/profile/programs/bseu/economic-informatics", headers=headers)
    client.put("/api/profile/programs/alpha/accounting", headers=headers)

    first = client.get("/api/profile/saved", headers=headers)
    second = client.get("/api/profile/saved", headers=headers)
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert [item["university"]["slug"] for item in first.json()["universities"]] == [
        "alpha",
        "bseu",
    ]
    assert [item["program"]["slug"] for item in first.json()["programs"]] == [
        "accounting",
        "economic-informatics",
    ]
    assert first.json()["programs"][0]["monitoring_state"] == "unsupported"


def test_database_uniqueness_and_profile_cascade_constraints(
    profile_api: tuple[TestClient, sessionmaker[Session], dict[str, int]],
) -> None:
    client, session_factory, ids = profile_api
    _token, headers = create_profile(client)
    client.put("/api/profile/universities/bseu", headers=headers)
    client.put("/api/profile/programs/bseu/economic-informatics", headers=headers)

    with session_factory() as session:
        profile = session.scalar(select(AnonymousProfile))
        assert profile is not None
        session.add(
            SavedUniversity(
                profile_id=profile.id,
                university_id=ids["bseu_university"],
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        session.delete(profile)
        session.commit()
        assert session.scalar(select(func.count()).select_from(SavedUniversity)) == 0
        assert session.scalar(select(func.count()).select_from(SavedProgram)) == 0
        assert session.get(University, ids["bseu_university"]) is not None
        assert session.get(Program, ids["bseu_program"]) is not None


def test_profile_api_isolated_from_external_network_and_documents_typed_routes(
    profile_api: tuple[TestClient, sessionmaker[Session], dict[str, int]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _session_factory, _ids = profile_api

    def fail_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("profile API attempted an external connection")

    monkeypatch.setattr(socket, "create_connection", fail_network)
    _token, headers = create_profile(client)
    assert client.get("/api/profile/saved", headers=headers).status_code == 200
    paths = client.get("/openapi.json").json()["paths"]
    assert set(paths) == {
        "/api/profile",
        "/api/profile/score",
        "/api/profile/saved",
        "/api/profile/universities/{university_slug}",
        "/api/profile/programs/{university_slug}/{program_slug}",
        "/api/profile/watches",
            "/api/profile/watch-events",
            "/api/profile/watches/{university_slug}/{program_slug}",
            "/api/profile/telegram",
            "/api/profile/telegram/challenge",
        }
