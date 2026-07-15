import json
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from .bseu_mapping import BSEU_CODE
from .calculations import AdmissionMetrics, calculate_metrics
from .catalog_models import LegacySpecialtyMapping, MonitoringStatus, Program, ProgramOffering, University, utc_now
from .catalog_repository import program_by_university_and_slug, university_by_slug
from .catalog_service import CatalogNotFoundError, offering_latest
from .config import get_settings
from .models import AdmissionSnapshot
from .profile_models import AnonymousProfile
from .watch_models import ProgramWatch, ProgramWatchEvent
from .watch_repository import (
    active_watch_rows,
    active_watches_for_program,
    add_watch_event,
    disable_watch_record,
    enable_watch_record,
    profile_event_rows,
    saved_program_exists,
)
from .watch_schemas import (
    ProgramWatchEventResponse,
    ProgramWatchMutationResponse,
    ProgramWatchResponse,
    WatchProgramResponse,
    WatchUniversityResponse,
)


class ProgramWatchDomainError(RuntimeError):
    pass


class ProgramWatchUnsupportedError(ProgramWatchDomainError):
    pass


class ProgramWatchRequiresSavedProgramError(ProgramWatchDomainError):
    pass


def resolve_program(session: Session, university_slug: str, program_slug: str) -> Program:
    university = university_by_slug(session, university_slug)
    if university is None:
        raise CatalogNotFoundError("Университет не найден")
    row = program_by_university_and_slug(session, university.id, program_slug)
    if row is None:
        raise CatalogNotFoundError("Программа не найдена")
    return row.program


def watchable_offering_for_program(
    session: Session, program: Program
) -> ProgramOffering | None:
    return session.scalar(
        select(ProgramOffering)
        .join(Program, Program.id == ProgramOffering.program_id)
        .join(University, University.id == Program.university_id)
        .join(
            LegacySpecialtyMapping,
            LegacySpecialtyMapping.program_offering_id == ProgramOffering.id,
        )
        .where(
            ProgramOffering.program_id == program.id,
            ProgramOffering.monitoring_supported.is_(True),
            ProgramOffering.monitoring_status == MonitoringStatus.ONLINE,
            University.code == BSEU_CODE,
        )
        .order_by(ProgramOffering.admission_year.desc(), ProgramOffering.id)
        .limit(1)
    )


def _latest_usable_snapshot(
    session: Session, offering: ProgramOffering
) -> AdmissionSnapshot | None:
    try:
        public_snapshot = offering_latest(
            session,
            offering.id,
            stale_after_minutes=get_settings().stale_after_minutes,
        )
    except CatalogNotFoundError:
        return None
    if public_snapshot.is_stale:
        return None
    return session.get(AdmissionSnapshot, public_snapshot.id)


def _watch_response(watch: ProgramWatch) -> ProgramWatchResponse:
    program = watch.program
    university = program.university
    return ProgramWatchResponse(
        enabled=watch.enabled,
        created_at=watch.created_at,
        updated_at=watch.updated_at,
        university=WatchUniversityResponse(
            slug=university.slug,
            short_name=university.short_name,
            full_name=university.full_name,
        ),
        program=WatchProgramResponse(slug=program.slug, name=program.name),
    )


def enable_program_watch(
    session: Session,
    profile: AnonymousProfile,
    university_slug: str,
    program_slug: str,
) -> ProgramWatchResponse:
    program = resolve_program(session, university_slug, program_slug)
    if not saved_program_exists(session, profile.id, program.id):
        raise ProgramWatchRequiresSavedProgramError(
            "Сначала сохраните программу в личный список"
        )
    offering = watchable_offering_for_program(session, program)
    if offering is None:
        raise ProgramWatchUnsupportedError(
            "Мониторинг пока недоступен для этой программы"
        )
    baseline = _latest_usable_snapshot(session, offering)
    watch = enable_watch_record(
        session,
        profile,
        program,
        baseline.id if baseline is not None else None,
    )
    watch.program = program
    return _watch_response(watch)


def disable_program_watch(
    session: Session,
    profile: AnonymousProfile,
    university_slug: str,
    program_slug: str,
) -> ProgramWatchMutationResponse:
    program = resolve_program(session, university_slug, program_slug)
    disable_watch_record(session, profile, program)
    return ProgramWatchMutationResponse(
        university_slug=university_slug,
        program_slug=program_slug,
        enabled=False,
    )


def disable_watch_for_removed_program(
    session: Session, profile: AnonymousProfile, program: Program
) -> None:
    disable_watch_record(session, profile, program)


def list_active_program_watches(
    session: Session, profile: AnonymousProfile
) -> list[ProgramWatchResponse]:
    return [_watch_response(watch) for watch in active_watch_rows(session, profile.id)]


def _cutoff_value(snapshot: AdmissionSnapshot) -> dict[str, int | bool | None] | None:
    has_competition = snapshot.applications_total > snapshot.admission_plan
    if has_competition and (
        snapshot.estimated_cutoff_min is None or snapshot.estimated_cutoff_max is None
    ):
        return None
    return {
        "has_competition": has_competition,
        "minimum": snapshot.estimated_cutoff_min,
        "maximum": snapshot.estimated_cutoff_max,
    }


def _score_metrics(snapshot: AdmissionSnapshot, score: int) -> AdmissionMetrics:
    distribution = json.loads(snapshot.distribution_json)
    return calculate_metrics(
        snapshot.admission_plan,
        snapshot.applications_total,
        distribution,
        score,
    )


def _changes_for_watch(
    watch: ProgramWatch,
    previous: AdmissionSnapshot,
    current: AdmissionSnapshot,
) -> list[tuple[str, object, object]]:
    changes: list[tuple[str, object, object]] = []
    if previous.applications_total != current.applications_total:
        changes.append(
            (
                "applications_total_changed",
                previous.applications_total,
                current.applications_total,
            )
        )
    previous_cutoff = _cutoff_value(previous)
    current_cutoff = _cutoff_value(current)
    if (
        previous_cutoff is not None
        and current_cutoff is not None
        and previous_cutoff != current_cutoff
    ):
        changes.append(("estimated_cutoff_changed", previous_cutoff, current_cutoff))
    score = watch.profile.personal_score
    if score is None:
        return changes
    previous_metrics = _score_metrics(previous, score)
    current_metrics = _score_metrics(current, score)
    if "Недостаточно данных" in (previous_metrics.status, current_metrics.status):
        return changes
    if previous_metrics.estimated_user_position != current_metrics.estimated_user_position:
        changes.append(
            (
                "user_position_changed",
                previous_metrics.estimated_user_position,
                current_metrics.estimated_user_position,
            )
        )
    if previous_metrics.status != current_metrics.status:
        changes.append(
            ("user_status_changed", previous_metrics.status, current_metrics.status)
        )
    return changes


def evaluate_program_watches(
    session: Session, source_snapshot_ids: Iterable[int]
) -> int:
    created = 0
    for snapshot_id in sorted(set(source_snapshot_ids)):
        current = session.get(AdmissionSnapshot, snapshot_id)
        if current is None or current.program_offering_id is None:
            continue
        offering = session.get(ProgramOffering, current.program_offering_id)
        if offering is None:
            continue
        latest = _latest_usable_snapshot(session, offering)
        if latest is None or latest.id != current.id:
            continue
        watches = active_watches_for_program(session, offering.program_id)
        for watch in watches:
            previous_id = watch.last_evaluated_snapshot_id
            if previous_id is None:
                watch.last_evaluated_snapshot_id = current.id
                watch.updated_at = utc_now()
                continue
            if previous_id >= current.id:
                continue
            previous = session.get(AdmissionSnapshot, previous_id)
            if previous is None or previous.program_offering_id != current.program_offering_id:
                watch.last_evaluated_snapshot_id = current.id
                watch.updated_at = utc_now()
                continue
            for event_kind, previous_value, current_value in _changes_for_watch(
                watch, previous, current
            ):
                add_watch_event(
                    session,
                    watch,
                    current.id,
                    event_kind,
                    previous_value,
                    current_value,
                )
                created += 1
            watch.last_evaluated_snapshot_id = current.id
            watch.updated_at = utc_now()
    session.commit()
    return created


def _cutoff_label(value: object) -> str:
    if not isinstance(value, dict):
        return "недоступно"
    if value.get("has_competition") is False:
        return "конкурс пока отсутствует"
    minimum = value.get("minimum")
    maximum = value.get("maximum")
    if not isinstance(minimum, int) or not isinstance(maximum, int):
        return "недоступно"
    return str(minimum) if minimum == maximum else f"{minimum}–{maximum}"


def event_description(event: ProgramWatchEvent) -> str:
    previous = event.previous_value
    current = event.current_value
    if event.event_kind == "applications_total_changed":
        return f"Количество заявлений изменилось: {previous} → {current}."
    if event.event_kind == "estimated_cutoff_changed":
        return (
            "Предполагаемый проходной диапазон изменился: "
            f"{_cutoff_label(previous)} → {_cutoff_label(current)}."
        )
    if event.event_kind == "user_position_changed":
        return f"Примерное место изменилось: {previous} → {current}."
    if event.event_kind == "user_status_changed":
        return f"Статус для вашего балла изменился: «{previous}» → «{current}»."
    return "Данные мониторинга изменились."


def list_program_watch_events(
    session: Session, profile: AnonymousProfile
) -> list[ProgramWatchEventResponse]:
    responses: list[ProgramWatchEventResponse] = []
    for event in profile_event_rows(session, profile.id):
        program = event.watch.program
        university = program.university
        responses.append(
            ProgramWatchEventResponse(
                event_kind=event.event_kind,
                description=event_description(event),
                created_at=event.created_at,
                telegram_delivery_status=_telegram_delivery_status(event),
                university=WatchUniversityResponse(
                    slug=university.slug,
                    short_name=university.short_name,
                    full_name=university.full_name,
                ),
                program=WatchProgramResponse(slug=program.slug, name=program.name),
            )
        )
    return responses


def _telegram_delivery_status(
    event: ProgramWatchEvent,
) -> str | None:
    states = {delivery.state for delivery in event.telegram_deliveries}
    if "confirmed" in states:
        return "confirmed"
    if states & {"pending", "retryable"}:
        return "pending"
    if states:
        return "failed"
    return None
