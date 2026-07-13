from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .catalog_models import DataSource, SourceHealth
from .models import HttpCacheState, ScraperRun


def data_source_for_url(session: Session, source_url: str) -> DataSource | None:
    return session.scalar(select(DataSource).where(DataSource.source_url == source_url))


def attach_run_to_source(
    session: Session, run: ScraperRun, source_url: str, started_at: datetime
) -> DataSource | None:
    source = data_source_for_url(session, source_url)
    if source is not None:
        run.data_source_id = source.id
        source.last_attempt_at = started_at
    return source


def record_source_success(
    source: DataSource | None,
    cache: HttpCacheState | None,
    finished_at: datetime,
) -> None:
    if source is None:
        return
    source.last_attempt_at = finished_at
    source.last_success_at = finished_at
    source.last_error_type = None
    source.last_error_message = None
    source.consecutive_failures = 0
    source.health_status = SourceHealth.HEALTHY
    if cache is not None:
        source.etag = cache.etag
        source.last_modified = cache.last_modified


def record_source_error(source: DataSource | None, run: ScraperRun) -> None:
    if source is None:
        return
    source.last_attempt_at = run.finished_at
    source.last_error_type = run.error_type
    source.last_error_message = run.error_message
    source.consecutive_failures += 1
    source.health_status = SourceHealth.DEGRADED
