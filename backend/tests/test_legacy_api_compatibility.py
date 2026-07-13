from collections.abc import Iterator
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from test_bseu_backfill import seed_core_database, sqlite_url

from alembic import command
from app import main
from app.database import get_db
from app.schema import make_alembic_config

LEGACY_SNAPSHOT_KEYS = {
    "id",
    "specialty_id",
    "specialty",
    "study_form",
    "funding_type",
    "source_url",
    "fetched_at",
    "source_updated_at",
    "admission_plan",
    "applications_total",
    "competition",
    "estimated_cutoff_min",
    "estimated_cutoff_max",
    "estimated_cutoff",
    "no_competition",
    "user_score",
    "estimated_user_position",
    "user_status",
    "distribution",
}


def test_all_legacy_api_contracts_remain_compatible(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    database = tmp_path / "legacy-api.db"
    seed_core_database(database)
    command.upgrade(make_alembic_config(sqlite_url(database)), "head")
    engine = create_engine(sqlite_url(database))
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_db() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    async def fake_refresh() -> dict:
        return {"status": "success", "changed": False, "snapshot_created": False, "created": 0, "rows_found": 77}

    main.app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(main.scraper, "refresh", fake_refresh)
    client = TestClient(main.app)
    try:
        health = client.get("/api/health")
        assert health.status_code == 200
        assert set(health.json()) == {
            "status",
            "database",
            "scheduler_running",
            "refresh_in_progress",
            "last_success_at",
            "last_error",
        }

        config = client.get("/api/config")
        assert config.status_code == 200
        assert set(config.json()) == {
            "university",
            "target_specialties",
            "study_form",
            "funding_type",
            "user_score",
            "poll_interval_minutes",
            "timezone",
            "source_url",
            "stale_after_minutes",
            "telegram_enabled",
        }

        specialties = client.get("/api/specialties")
        assert specialties.status_code == 200
        assert specialties.json() == [
            {
                "id": 17,
                "display_name": "Экономическая информатика",
                "study_form": "дневная",
                "funding_type": "платная",
                "source_url": "https://bseu.by/abiturient/",
            }
        ]

        latest = client.get("/api/specialties/17/latest")
        assert latest.status_code == 200
        latest_payload = latest.json()
        assert set(latest_payload) == LEGACY_SNAPSHOT_KEYS | {
            "last_checked_at",
            "data_age_seconds",
            "source_age_seconds",
            "is_stale",
        }
        assert latest_payload["id"] == 72
        assert latest_payload["applications_total"] == 25

        history = client.get("/api/specialties/17/history")
        assert history.status_code == 200
        assert [item["id"] for item in history.json()] == [72, 71]
        assert all(set(item) == LEGACY_SNAPSHOT_KEYS for item in history.json())

        distribution = client.get("/api/specialties/17/score-distribution")
        assert distribution.status_code == 200
        assert set(distribution.json()) == {"specialty_id", "fetched_at", "distribution"}

        status = client.get("/api/status")
        assert status.status_code == 200
        assert set(status.json()) == {"state", "last_run", "consecutive_errors", "next_run_at"}

        refresh = client.post(
            "/api/refresh",
            headers={"X-Refresh-Token": main.settings.manual_refresh_token},
        )
        assert refresh.status_code == 200
        assert refresh.json()["status"] == "success"
    finally:
        main.app.dependency_overrides.clear()
        engine.dispose()
