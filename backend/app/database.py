from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from .catalog_search import register_catalog_sqlite_functions
from .config import get_settings, resolve_database_url
from .schema import ensure_schema_current

settings = get_settings()
database_url = resolve_database_url(settings.database_url)

connect_args = {"check_same_thread": False, "timeout": 30} if database_url.startswith("sqlite") else {}
engine = create_engine(database_url, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

if database_url.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def configure_sqlite(dbapi_connection, _connection_record):  # type: ignore[no-untyped-def]
        register_catalog_sqlite_functions(dbapi_connection)
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def init_db() -> None:
    """Compatibility name: validate the Alembic revision without creating or migrating schema."""
    ensure_schema_current(engine)


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session
