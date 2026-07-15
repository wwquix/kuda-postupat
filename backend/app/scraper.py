import asyncio
import hashlib
import logging
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import desc, select

from .adapters import MonitoringAdapterRegistry, UnknownMonitoringAdapterError
from .bseu_mapping import ensure_bseu_mapping_for_specialty
from .calculations import calculate_metrics
from .config import Settings
from .database import SessionLocal
from .models import AdmissionSnapshot, HttpCacheState, ScraperRun
from .parser import ParserError
from .repository import get_or_create_specialty, save_snapshot_if_changed
from .source_runtime import attach_run_to_source, record_source_error, record_source_success
from .telegram import TelegramDeliveryError, build_change_message, send_once

logger = logging.getLogger(__name__)


class RefreshInProgressError(RuntimeError):
    pass


class RefreshTooSoonError(RuntimeError):
    pass


class NotModifiedWithoutSnapshotError(RuntimeError):
    pass


class AdmissionScraper:
    def __init__(self, settings: Settings, adapter_registry: MonitoringAdapterRegistry):
        self.settings = settings
        self.adapter_registry = adapter_registry
        self._lock = asyncio.Lock()

    async def _fetch(self, source_url: str, headers: dict[str, str]) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(self.settings.request_retries):
            try:
                async with httpx.AsyncClient(
                    timeout=self.settings.request_timeout_seconds,
                    follow_redirects=True,
                    headers={"User-Agent": "BGEU-Admission-Monitor/1.0 (+local deployment)"},
                ) as client:
                    response = await client.get(source_url, headers=headers)
                if response.status_code == 304:
                    return response
                if response.status_code >= 500:
                    raise httpx.HTTPStatusError("Upstream server error", request=response.request, response=response)
                response.raise_for_status()
                return response
            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                last_error = exc
                if attempt + 1 < self.settings.request_retries:
                    await asyncio.sleep(2**attempt)
        assert last_error is not None
        raise last_error

    async def refresh(self, adapter_key: str, *, force: bool = False) -> dict:
        if self._lock.locked():
            raise RefreshInProgressError("Обновление уже выполняется")
        async with self._lock:
            started = datetime.now(UTC)
            with SessionLocal() as session:
                try:
                    adapter = self.adapter_registry.get(adapter_key)
                except UnknownMonitoringAdapterError as exc:
                    run = ScraperRun(started_at=started, status="running", rows_found=0)
                    session.add(run)
                    session.commit()
                    run.status = "error"
                    run.finished_at = datetime.now(UTC)
                    run.error_type = type(exc).__name__
                    run.error_message = str(exc)[:2000]
                    session.commit()
                    raise
                last_run = session.scalar(
                    select(ScraperRun)
                    .where(ScraperRun.status.in_(["success", "not_modified"]))
                    .order_by(desc(ScraperRun.started_at))
                    .limit(1)
                )
                last_started = (
                    last_run.started_at.replace(tzinfo=UTC)
                    if last_run and last_run.started_at.tzinfo is None
                    else (last_run.started_at if last_run else None)
                )
                if not force and last_started and started - last_started < timedelta(minutes=5):
                    raise RefreshTooSoonError("Повторный запрос разрешен не чаще одного раза в 5 минут")
                run = ScraperRun(started_at=started, status="running", rows_found=0)
                session.add(run)
                source = attach_run_to_source(session, run, adapter.source_url, started)
                session.commit()
                cache = session.get(HttpCacheState, adapter.source_url)
                headers = {}
                if cache and cache.etag:
                    headers["If-None-Match"] = cache.etag
                if cache and cache.last_modified:
                    headers["If-Modified-Since"] = cache.last_modified
                try:
                    previous_runs = session.scalars(
                        select(ScraperRun)
                        .where(ScraperRun.id != run.id)
                        .order_by(desc(ScraperRun.started_at))
                        .limit(20)
                    ).all()
                    previous_consecutive_errors = 0
                    for previous_run in previous_runs:
                        if previous_run.status != "error":
                            break
                        previous_consecutive_errors += 1
                    response = await self._fetch(adapter.source_url, headers)
                    run.http_status = response.status_code
                    if response.status_code == 304:
                        has_snapshot = session.scalar(select(AdmissionSnapshot.id).limit(1)) is not None
                        if not has_snapshot:
                            response = await self._fetch(adapter.source_url, {})
                            run.http_status = response.status_code
                            if response.status_code == 304:
                                raise NotModifiedWithoutSnapshotError(
                                    "Источник вернул 304, но сохраненных данных для использования нет"
                                )
                        else:
                            run.status = "not_modified"
                            run.finished_at = datetime.now(UTC)
                            if cache:
                                cache.checked_at = run.finished_at
                            record_source_success(source, cache, run.finished_at)
                            session.commit()
                            return {
                                "status": "not_modified",
                                "changed": False,
                                "snapshot_created": False,
                                "created": 0,
                                "rows_found": 0,
                                "message": "Источник доступен, данные не изменились",
                            }
                    if len(response.content) < 100:
                        raise ParserError("Источник вернул подозрительно короткий документ")
                    parsed = adapter.parse(response.content, response.headers.get("content-type"))
                    rows = parsed.rows
                    selected = parsed.selected
                    run.rows_found = len(rows)
                    run.content_hash = hashlib.sha256(response.content).hexdigest()
                    created = 0
                    messages: list[str] = []
                    for row in selected:
                        specialty = get_or_create_specialty(session, row, adapter.source_page_url)
                        program_offering_id = ensure_bseu_mapping_for_specialty(session, specialty)
                        metrics = calculate_metrics(
                            row.admission_plan, row.applications_total, row.distribution, self.settings.user_score
                        )
                        snapshot, previous, was_created = save_snapshot_if_changed(
                            session,
                            specialty,
                            row,
                            self.settings.user_score,
                            metrics,
                            program_offering_id,
                        )
                        created += int(was_created)
                        if was_created:
                            message = build_change_message(specialty, snapshot, previous)
                            if message:
                                messages.append(message)
                    if cache is None:
                        cache = HttpCacheState(url=adapter.source_url)
                        session.add(cache)
                    cache.etag = response.headers.get("etag")
                    cache.last_modified = response.headers.get("last-modified")
                    cache.checked_at = datetime.now(UTC)
                    run.status = "success"
                    run.finished_at = datetime.now(UTC)
                    record_source_success(source, cache, run.finished_at)
                    session.commit()
                    for message in messages:
                        try:
                            await send_once(session, self.settings, message)
                        except TelegramDeliveryError:
                            logger.warning("Telegram notification failed")
                    if previous_consecutive_errors >= 3:
                        try:
                            await send_once(
                                session,
                                self.settings,
                                "БГЭУ — источник снова доступен после трех последовательных ошибок.",
                            )
                        except TelegramDeliveryError:
                            logger.warning("Telegram recovery notification failed")
                    return {
                        "status": "success",
                        "changed": created > 0,
                        "snapshot_created": created > 0,
                        "created": created,
                        "rows_found": len(rows),
                    }
                except Exception as exc:
                    logger.exception("Admission refresh failed")
                    run.status = "error"
                    run.finished_at = datetime.now(UTC)
                    run.error_type = type(exc).__name__
                    run.error_message = str(exc)[:2000]
                    if isinstance(exc, httpx.HTTPStatusError):
                        run.http_status = exc.response.status_code
                    record_source_error(source, run)
                    session.commit()
                    recent_runs = session.scalars(
                        select(ScraperRun).order_by(desc(ScraperRun.started_at)).limit(3)
                    ).all()
                    if len(recent_runs) == 3 and all(item.status == "error" for item in recent_runs):
                        try:
                            await send_once(
                                session,
                                self.settings,
                                "БГЭУ — источник недоступен три проверки подряд. "
                                "Последние корректные данные сохранены.",
                            )
                        except TelegramDeliveryError:
                            logger.warning("Telegram outage notification failed")
                    raise
