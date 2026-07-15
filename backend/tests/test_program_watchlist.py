from __future__ import annotations

import json
import socket
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
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
from app.models import AdmissionSnapshot, NotificationLog, Specialty
from app.profile_api import router
from app.profile_models import AnonymousProfile
from app.watch_models import ProgramWatch, ProgramWatchEvent
from app.watch_service import evaluate_program_watches


@pytest.fixture
def watch_api(
    tmp_path: Path,
    test_engine_factory: Callable[[str], Engine],
) -> tuple[TestClient, sessionmaker[Session], dict[str, int]]:
    database = tmp_path / "program-watchlist.db"
    engine = test_engine_factory(f"sqlite:///{database.as_posix()}")
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    now = datetime.now(UTC)
    with factory() as session:
        alpha = University(
            code="alpha",
            slug="alpha",
            short_name="Альфа",
            full_name="Альфа университет",
            institution_kind=InstitutionKind.UNIVERSITY,
            ownership_type=OwnershipType.STATE,
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
            official_site_url="https://bseu.by",
            monitoring_status=MonitoringStatus.ONLINE,
            source_url="https://edu.gov.by/registry",
            source_checked_at=now,
        )
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
        session.add_all(
            [alpha, bseu, alpha_program, bseu_program, offering, specialty, source]
        )
        session.flush()
        session.add(
            LegacySpecialtyMapping(
                legacy_specialty_id=specialty.id,
                program_id=bseu_program.id,
                program_offering_id=offering.id,
                mapping_version=1,
            )
        )
        session.commit()
        ids = {
            "alpha_program": alpha_program.id,
            "bseu_program": bseu_program.id,
            "offering": offering.id,
            "specialty": specialty.id,
        }

    def override_db() -> Iterator[Session]:
        with factory() as session:
            yield session

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = override_db
    return TestClient(app), factory, ids


def create_profile(client: TestClient) -> tuple[str, dict[str, str]]:
    response = client.post("/api/profile")
    assert response.status_code == 201
    token = response.json()["token"]
    return token, {"Authorization": f"Bearer {token}"}


def save_bseu_program(client: TestClient, headers: dict[str, str]) -> None:
    response = client.put(
        "/api/profile/programs/bseu/economic-informatics", headers=headers
    )
    assert response.status_code == 200
    assert response.json()["programs"][0]["watch_supported"] is True


def add_snapshot(
    factory: sessionmaker[Session],
    ids: dict[str, int],
    *,
    applications_total: int,
    distribution: dict[str, int],
    sequence: int,
    source_updated_at: datetime | None = None,
) -> int:
    metrics = calculate_metrics(3, applications_total, distribution, 276)
    fetched_at = datetime.now(UTC) + timedelta(seconds=sequence)
    with factory() as session:
        snapshot = AdmissionSnapshot(
            specialty_id=ids["specialty"],
            program_offering_id=ids["offering"],
            fetched_at=fetched_at,
            source_updated_at=(source_updated_at or fetched_at).astimezone(
                ZoneInfo("Europe/Minsk")
            ),
            admission_plan=3,
            applications_total=applications_total,
            competition=metrics.competition,
            estimated_cutoff_min=metrics.cutoff_min,
            estimated_cutoff_max=metrics.cutoff_max,
            user_score=276,
            estimated_user_position=metrics.estimated_user_position,
            user_status=metrics.status,
            distribution_json=json.dumps(distribution, sort_keys=True),
            raw_data_hash=f"{sequence:064x}",
        )
        session.add(snapshot)
        source = session.scalar(select(DataSource).where(DataSource.university_id == 2))
        if source is not None:
            source.last_attempt_at = fetched_at
            source.last_success_at = fetched_at
        session.commit()
        return snapshot.id


def test_watch_enable_disable_idempotency_and_supported_scope(
    watch_api: tuple[TestClient, sessionmaker[Session], dict[str, int]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, factory, _ids = watch_api

    def fail_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("watch API attempted external access")

    monkeypatch.setattr(socket, "create_connection", fail_network)
    _token, headers = create_profile(client)
    save_bseu_program(client, headers)

    for _ in range(2):
        enabled = client.put(
            "/api/profile/watches/bseu/economic-informatics", headers=headers
        )
        assert enabled.status_code == 200
        assert enabled.json()["enabled"] is True
    watches = client.get("/api/profile/watches", headers=headers)
    assert watches.status_code == 200
    assert [item["program"]["slug"] for item in watches.json()] == [
        "economic-informatics"
    ]
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(ProgramWatch)) == 1

    for _ in range(2):
        disabled = client.delete(
            "/api/profile/watches/bseu/economic-informatics", headers=headers
        )
        assert disabled.status_code == 200
        assert disabled.json()["enabled"] is False
    assert client.get("/api/profile/watches", headers=headers).json() == []

    client.put("/api/profile/programs/alpha/accounting", headers=headers)
    unsupported = client.put("/api/profile/watches/alpha/accounting", headers=headers)
    assert unsupported.status_code == 409
    assert unsupported.json() == {
        "detail": "Мониторинг пока недоступен для этой программы"
    }
    assert (
        client.put(
            "/api/profile/watches/alpha/economic-informatics", headers=headers
        ).status_code
        == 404
    )
    assert client.put(
        "/api/profile/watches/unknown/economic-informatics", headers=headers
    ).status_code == 404
    assert client.put(
        "/api/profile/watches/bseu/unknown", headers=headers
    ).status_code == 404
    assert client.get("/api/profile/watches", headers={}).status_code == 401
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(NotificationLog)) == 0


def test_first_usable_snapshot_establishes_baseline_without_false_event(
    watch_api: tuple[TestClient, sessionmaker[Session], dict[str, int]],
) -> None:
    client, factory, ids = watch_api
    _token, headers = create_profile(client)
    save_bseu_program(client, headers)
    assert (
        client.put(
            "/api/profile/watches/bseu/economic-informatics", headers=headers
        ).status_code
        == 200
    )
    first_snapshot = add_snapshot(
        factory,
        ids,
        applications_total=5,
        distribution={"300-309": 1, "290-299": 2, "280-289": 2},
        sequence=1,
    )
    with factory() as session:
        assert evaluate_program_watches(session, [first_snapshot]) == 0
        watch = session.scalar(select(ProgramWatch))
        assert watch is not None
        assert watch.last_evaluated_snapshot_id == first_snapshot
        assert session.scalar(select(func.count()).select_from(ProgramWatchEvent)) == 0
    assert client.get("/api/profile/watch-events", headers=headers).json() == []


def test_meaningful_events_score_semantics_deduplication_and_profile_isolation(
    watch_api: tuple[TestClient, sessionmaker[Session], dict[str, int]],
) -> None:
    client, factory, ids = watch_api
    _first_token, first_headers = create_profile(client)
    _second_token, second_headers = create_profile(client)
    first = add_snapshot(
        factory,
        ids,
        applications_total=5,
        distribution={"300-309": 1, "290-299": 2, "280-289": 2},
        sequence=1,
    )
    for headers in (first_headers, second_headers):
        save_bseu_program(client, headers)
        assert (
            client.put(
                "/api/profile/watches/bseu/economic-informatics", headers=headers
            ).status_code
            == 200
        )
    assert client.patch(
        "/api/profile/score", headers=first_headers, json={"score": 292}
    ).status_code == 200

    second = add_snapshot(
        factory,
        ids,
        applications_total=6,
        distribution={"300-309": 3, "290-299": 2, "280-289": 1},
        sequence=2,
    )
    with factory() as session:
        assert evaluate_program_watches(session, [second]) == 6
        assert evaluate_program_watches(session, [second]) == 0
        assert session.scalar(select(func.count()).select_from(ProgramWatchEvent)) == 6
        assert session.scalar(select(func.count()).select_from(NotificationLog)) == 0

    first_events = client.get(
        "/api/profile/watch-events", headers=first_headers
    ).json()
    second_events = client.get(
        "/api/profile/watch-events", headers=second_headers
    ).json()
    assert {item["event_kind"] for item in first_events} == {
        "applications_total_changed",
        "estimated_cutoff_changed",
        "user_position_changed",
        "user_status_changed",
    }
    assert [item["event_kind"] for item in first_events] == [
        "user_status_changed",
        "user_position_changed",
        "estimated_cutoff_changed",
        "applications_total_changed",
    ]
    assert {item["event_kind"] for item in second_events} == {
        "applications_total_changed",
        "estimated_cutoff_changed",
    }
    assert all(
        set(item)
        == {"event_kind", "description", "created_at", "university", "program"}
        for item in first_events + second_events
    )
    assert all("→" in item["description"] for item in first_events + second_events)
    assert all(item["program"]["slug"] == "economic-informatics" for item in first_events)
    _third_token, third_headers = create_profile(client)
    assert client.get("/api/profile/watches", headers=third_headers).json() == []
    assert client.get("/api/profile/watch-events", headers=third_headers).json() == []
    assert first != second


def test_stale_snapshot_and_removed_saved_program_do_not_generate_events(
    watch_api: tuple[TestClient, sessionmaker[Session], dict[str, int]],
) -> None:
    client, factory, ids = watch_api
    _token, headers = create_profile(client)
    first = add_snapshot(
        factory,
        ids,
        applications_total=5,
        distribution={"300-309": 1, "290-299": 2, "280-289": 2},
        sequence=1,
    )
    save_bseu_program(client, headers)
    client.put("/api/profile/watches/bseu/economic-informatics", headers=headers)
    stale = add_snapshot(
        factory,
        ids,
        applications_total=6,
        distribution={"300-309": 3, "290-299": 2, "280-289": 1},
        sequence=2,
        source_updated_at=datetime.now(UTC) - timedelta(days=2),
    )
    with factory() as session:
        assert evaluate_program_watches(session, [stale]) == 0
        watch = session.scalar(select(ProgramWatch))
        assert watch is not None
        assert watch.last_evaluated_snapshot_id == first
    removed = client.delete(
        "/api/profile/programs/bseu/economic-informatics", headers=headers
    )
    assert removed.status_code == 200
    assert client.get("/api/profile/watches", headers=headers).json() == []
    with factory() as session:
        watch = session.scalar(select(ProgramWatch))
        assert watch is not None
        assert watch.enabled is False


def test_profile_deletion_cascades_only_profile_owned_watch_data(
    watch_api: tuple[TestClient, sessionmaker[Session], dict[str, int]],
) -> None:
    client, factory, ids = watch_api
    _token, headers = create_profile(client)
    add_snapshot(
        factory,
        ids,
        applications_total=5,
        distribution={"300-309": 1, "290-299": 2, "280-289": 2},
        sequence=1,
    )
    save_bseu_program(client, headers)
    client.put("/api/profile/watches/bseu/economic-informatics", headers=headers)
    with factory() as session:
        profile = session.scalar(select(AnonymousProfile))
        assert profile is not None
        session.delete(profile)
        session.commit()
        assert session.scalar(select(func.count()).select_from(ProgramWatch)) == 0
        assert session.scalar(select(func.count()).select_from(ProgramWatchEvent)) == 0
        assert session.get(Program, ids["bseu_program"]) is not None
        assert session.get(AdmissionSnapshot, 1) is not None
