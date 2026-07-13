from collections.abc import Iterator
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from test_bseu_backfill import seed_core_database, sqlite_url

from alembic import command
from app.catalog_api import router
from app.database import get_db
from app.schema import make_alembic_config


def client_for_database(path: Path) -> tuple[TestClient, object]:
    engine = create_engine(sqlite_url(path))
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_db() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = override_db
    return TestClient(app), engine


def test_catalog_api_reads_bseu_legacy_history_through_mapping(tmp_path: Path) -> None:
    database = tmp_path / "catalog-api.db"
    seed_core_database(database)
    command.upgrade(make_alembic_config(sqlite_url(database)), "head")
    with create_engine(sqlite_url(database)).connect() as connection:
        offering_id = connection.exec_driver_sql("SELECT id FROM program_offerings").scalar_one()
    client, engine = client_for_database(database)

    university = client.get("/api/universities/bseu")
    assert university.status_code == 200
    assert university.json()["code"] == "bseu"
    assert university.json()["categories"] == [{"code": "economic", "label_ru": "Экономика"}]

    programs = client.get("/api/universities/bseu/programs")
    assert programs.status_code == 200
    assert programs.json()[0]["code"] == "6-05-0311-05"
    assert programs.json()[0]["offerings"][0]["id"] == offering_id

    offering = client.get(f"/api/program-offerings/{offering_id}")
    assert offering.status_code == 200
    assert offering.json()["admission_year"] == 2026
    assert offering.json()["places"] == 60
    assert offering.json()["source"]["source_type"] == "admission_xml"

    latest = client.get(f"/api/program-offerings/{offering_id}/latest")
    assert latest.status_code == 200
    assert latest.json()["id"] == 72
    assert latest.json()["legacy_specialty_id"] == 17
    assert latest.json()["program_offering_id"] == offering_id
    assert latest.json()["applications_total"] == 25
    assert latest.json()["last_checked_at"] is not None

    history = client.get(f"/api/program-offerings/{offering_id}/history")
    assert history.status_code == 200
    assert [item["id"] for item in history.json()] == [72, 71]

    distribution = client.get(f"/api/program-offerings/{offering_id}/score-distribution")
    assert distribution.status_code == 200
    assert distribution.json()["snapshot_id"] == 72
    assert distribution.json()["distribution"] == [{"range": "270–279", "count": 11}]

    response_text = "\n".join(
        response.text for response in (university, programs, offering, latest, history, distribution)
    )
    assert "TELEGRAM_BOT_TOKEN" not in response_text
    assert "MANUAL_REFRESH_TOKEN" not in response_text
    assert client.get("/api/universities/unknown").status_code == 404
    assert client.get("/api/program-offerings/999999").status_code == 404
    engine.dispose()


def test_fresh_database_catalog_history_is_empty(tmp_path: Path) -> None:
    database = tmp_path / "fresh-catalog-api.db"
    command.upgrade(make_alembic_config(sqlite_url(database)), "head")
    with create_engine(sqlite_url(database)).connect() as connection:
        offering_id = connection.exec_driver_sql("SELECT id FROM program_offerings").scalar_one()
    client, engine = client_for_database(database)

    history = client.get(f"/api/program-offerings/{offering_id}/history")
    assert history.status_code == 200
    assert history.json() == []
    assert client.get(f"/api/program-offerings/{offering_id}/latest").status_code == 404
    assert client.get(f"/api/program-offerings/{offering_id}/score-distribution").status_code == 404
    engine.dispose()
