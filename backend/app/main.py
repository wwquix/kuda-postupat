import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from .adapters import BSEU_ADAPTER_KEY, build_bseu_monitoring_registry
from .catalog_api import router as catalog_router
from .config import get_settings
from .database import get_db, init_db
from .models import AdmissionSnapshot, ScraperRun, Specialty
from .profile_api import router as profile_router
from .repository import latest_snapshot, snapshot_to_dict
from .scraper import AdmissionScraper, RefreshInProgressError, RefreshTooSoonError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)
settings = get_settings()
adapter_registry = build_bseu_monitoring_registry(settings)
scraper = AdmissionScraper(settings, adapter_registry)
scheduler = AsyncIOScheduler(timezone=settings.timezone)


async def refresh_bseu() -> dict:
    return await scraper.refresh(BSEU_ADAPTER_KEY)


async def scheduled_refresh() -> None:
    try:
        await refresh_bseu()
    except RefreshTooSoonError:
        logger.info("Scheduled refresh skipped because of the five-minute limit")
    except Exception:
        logger.exception("Scheduled refresh failed; previous snapshots remain available")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    if settings.development_safe_mode:
        logger.info("Development-safe mode active; background scheduler and startup refresh are disabled")
        yield
        return
    scheduler.add_job(
        scheduled_refresh,
        "interval",
        minutes=settings.poll_interval_minutes,
        id="admission-refresh",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=120,
    )
    scheduler.start()
    initial_task = asyncio.create_task(scheduled_refresh())
    yield
    if not initial_task.done():
        initial_task.cancel()
    scheduler.shutdown(wait=False)


app = FastAPI(title="БГЭУ Admission Monitor API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Refresh-Token"],
)
app.include_router(catalog_router)
app.include_router(profile_router)


def _get_specialty(session: Session, specialty_id: int) -> Specialty:
    specialty = session.get(Specialty, specialty_id)
    if specialty is None or not specialty.active:
        raise HTTPException(status_code=404, detail="Специальность не найдена")
    return specialty


@app.get("/api/health")
def health(session: Session = Depends(get_db)) -> dict:
    last_success = session.scalar(
        select(ScraperRun)
        .where(ScraperRun.status.in_(["success", "not_modified"]))
        .order_by(desc(ScraperRun.finished_at))
        .limit(1)
    )
    last_error = session.scalar(
        select(ScraperRun).where(ScraperRun.status == "error").order_by(desc(ScraperRun.finished_at)).limit(1)
    )
    return {
        "status": "ok",
        "database": "ok",
        "scheduler_running": scheduler.running,
        "refresh_in_progress": scraper._lock.locked(),
        "last_success_at": last_success.finished_at if last_success else None,
        "last_error": last_error.error_message
        if last_error and (not last_success or last_error.started_at > last_success.started_at)
        else None,
    }


@app.get("/api/config")
def public_config() -> dict:
    return {
        "university": "БГЭУ",
        "target_specialties": settings.specialty_names,
        "study_form": settings.study_form,
        "funding_type": settings.funding_type,
        "user_score": settings.user_score,
        "poll_interval_minutes": settings.poll_interval_minutes,
        "timezone": settings.timezone,
        "source_url": settings.source_page_url,
        "stale_after_minutes": settings.stale_after_minutes,
        "telegram_enabled": settings.telegram_enabled,
    }


@app.get("/api/specialties")
def specialties(session: Session = Depends(get_db)) -> list[dict]:
    items = session.scalars(select(Specialty).where(Specialty.active.is_(True)).order_by(Specialty.display_name)).all()
    return [
        {
            "id": item.id,
            "display_name": item.display_name,
            "study_form": item.study_form,
            "funding_type": item.funding_type,
            "source_url": item.source_url,
        }
        for item in items
    ]


@app.get("/api/specialties/{specialty_id}/latest")
def specialty_latest(specialty_id: int, session: Session = Depends(get_db)) -> dict:
    specialty = _get_specialty(session, specialty_id)
    snapshot = latest_snapshot(session, specialty.id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Для специальности еще нет корректных данных")
    result = snapshot_to_dict(snapshot, specialty)
    fetched_at = snapshot.fetched_at.replace(tzinfo=UTC) if snapshot.fetched_at.tzinfo is None else snapshot.fetched_at
    now = datetime.now(UTC)
    last_success = session.scalar(
        select(ScraperRun)
        .where(ScraperRun.status.in_(["success", "not_modified"]))
        .order_by(desc(ScraperRun.finished_at))
        .limit(1)
    )
    checked_at = last_success.finished_at if last_success and last_success.finished_at else fetched_at
    if checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=UTC)
    checked_age = max(0, int((now - checked_at).total_seconds()))
    source_age: int | None = None
    if snapshot.source_updated_at:
        source_updated_at = snapshot.source_updated_at
        if source_updated_at.tzinfo is None:
            source_updated_at = source_updated_at.replace(tzinfo=ZoneInfo(settings.timezone))
        source_age = max(0, int((now - source_updated_at.astimezone(UTC)).total_seconds()))
    stale_after = settings.stale_after_minutes * 60
    result.update(
        {
            "last_checked_at": checked_at,
            "data_age_seconds": checked_age,
            "source_age_seconds": source_age,
            "is_stale": checked_age > stale_after or (source_age is not None and source_age > stale_after),
        }
    )
    return result


@app.get("/api/specialties/{specialty_id}/history")
def specialty_history(
    specialty_id: int,
    limit: int = Query(default=100, ge=1, le=1000),
    session: Session = Depends(get_db),
) -> list[dict]:
    specialty = _get_specialty(session, specialty_id)
    snapshots = session.scalars(
        select(AdmissionSnapshot)
        .where(AdmissionSnapshot.specialty_id == specialty.id)
        .order_by(desc(AdmissionSnapshot.fetched_at))
        .limit(limit)
    ).all()
    return [snapshot_to_dict(snapshot, specialty) for snapshot in snapshots]


@app.get("/api/specialties/{specialty_id}/score-distribution")
def score_distribution(specialty_id: int, session: Session = Depends(get_db)) -> dict:
    specialty = _get_specialty(session, specialty_id)
    snapshot = latest_snapshot(session, specialty.id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Для специальности еще нет корректных данных")
    return {
        "specialty_id": specialty.id,
        "fetched_at": snapshot.fetched_at,
        "distribution": [
            {"range": label.replace("-", "–"), "count": count}
            for label, count in sorted(
                json.loads(snapshot.distribution_json).items(),
                key=lambda item: int(item[0].split("-")[0]),
            )
        ],
    }


@app.get("/api/status")
def scraper_status(session: Session = Depends(get_db)) -> dict:
    last_run = session.scalar(select(ScraperRun).order_by(desc(ScraperRun.started_at)).limit(1))
    consecutive_errors = 0
    for run in session.scalars(select(ScraperRun).order_by(desc(ScraperRun.started_at)).limit(20)):
        if run.status != "error":
            break
        consecutive_errors += 1
    return {
        "state": "refreshing" if scraper._lock.locked() else (last_run.status if last_run else "never_run"),
        "last_run": {
            "started_at": last_run.started_at,
            "finished_at": last_run.finished_at,
            "status": last_run.status,
            "http_status": last_run.http_status,
            "error_type": last_run.error_type,
            "error_message": last_run.error_message,
            "rows_found": last_run.rows_found,
        }
        if last_run
        else None,
        "consecutive_errors": consecutive_errors,
        "next_run_at": scheduler.get_job("admission-refresh").next_run_time
        if scheduler.get_job("admission-refresh")
        else None,
    }


@app.post("/api/refresh", status_code=status.HTTP_200_OK)
async def manual_refresh(
    authorization: str | None = Header(default=None),
    x_refresh_token: str | None = Header(default=None),
) -> dict:
    token = x_refresh_token or (authorization.removeprefix("Bearer ") if authorization else None)
    if token != settings.manual_refresh_token:
        raise HTTPException(status_code=401, detail="Неверный токен ручного обновления")
    try:
        return await refresh_bseu()
    except RefreshInProgressError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RefreshTooSoonError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Manual refresh failed")
        raise HTTPException(status_code=502, detail="Не удалось получить корректные данные от источника") from exc
