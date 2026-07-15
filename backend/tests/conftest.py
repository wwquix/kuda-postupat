from collections.abc import Callable
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, event

from app import (  # noqa: F401 -- include every mapped table
    catalog_models,
    profile_models,
    telegram_watch_models,
    watch_models,
)
from app.catalog_search import register_catalog_sqlite_functions
from app.models import Base


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def test_engine_factory() -> Callable[[str], Engine]:
    engines: list[Engine] = []

    def create(url: str = "sqlite:///:memory:") -> Engine:
        engine = create_engine(url)

        @event.listens_for(engine, "connect")
        def enable_foreign_keys(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
            register_catalog_sqlite_functions(dbapi_connection)
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        Base.metadata.create_all(engine)
        engines.append(engine)
        return engine

    yield create
    for engine in engines:
        engine.dispose()
