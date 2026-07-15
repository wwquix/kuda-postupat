from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, joinedload

from .catalog_models import Program, University, utc_now
from .profile_models import AnonymousProfile, SavedProgram
from .watch_models import ProgramWatch, ProgramWatchEvent


def saved_program_exists(session: Session, profile_id: int, program_id: int) -> bool:
    return session.get(SavedProgram, (profile_id, program_id)) is not None


def watch_by_profile_program(
    session: Session, profile_id: int, program_id: int
) -> ProgramWatch | None:
    return session.scalar(
        select(ProgramWatch).where(
            ProgramWatch.profile_id == profile_id,
            ProgramWatch.program_id == program_id,
        )
    )


def enable_watch_record(
    session: Session,
    profile: AnonymousProfile,
    program: Program,
    baseline_snapshot_id: int | None,
) -> ProgramWatch:
    watch = watch_by_profile_program(session, profile.id, program.id)
    if watch is None:
        watch = ProgramWatch(
            profile_id=profile.id,
            program_id=program.id,
            enabled=True,
            last_evaluated_snapshot_id=baseline_snapshot_id,
        )
        session.add(watch)
    elif not watch.enabled:
        watch.enabled = True
        watch.last_evaluated_snapshot_id = baseline_snapshot_id
        watch.updated_at = utc_now()
    session.commit()
    session.refresh(watch)
    return watch


def disable_watch_record(
    session: Session, profile: AnonymousProfile, program: Program
) -> ProgramWatch | None:
    watch = watch_by_profile_program(session, profile.id, program.id)
    if watch is not None and watch.enabled:
        watch.enabled = False
        watch.updated_at = utc_now()
    session.commit()
    if watch is not None:
        session.refresh(watch)
    return watch


def active_watch_rows(session: Session, profile_id: int) -> list[ProgramWatch]:
    return list(
        session.scalars(
            select(ProgramWatch)
            .join(Program, Program.id == ProgramWatch.program_id)
            .join(University, University.id == Program.university_id)
            .where(ProgramWatch.profile_id == profile_id, ProgramWatch.enabled.is_(True))
            .options(joinedload(ProgramWatch.program).joinedload(Program.university))
            .order_by(
                func.catalog_normalize(University.full_name),
                func.catalog_normalize(Program.name),
                ProgramWatch.id,
            )
        ).all()
    )


def profile_event_rows(session: Session, profile_id: int) -> list[ProgramWatchEvent]:
    return list(
        session.scalars(
            select(ProgramWatchEvent)
            .join(ProgramWatch, ProgramWatch.id == ProgramWatchEvent.watch_id)
            .where(ProgramWatch.profile_id == profile_id)
            .options(
                joinedload(ProgramWatchEvent.watch)
                .joinedload(ProgramWatch.program)
                .joinedload(Program.university),
                joinedload(ProgramWatchEvent.telegram_deliveries),
            )
            .order_by(desc(ProgramWatchEvent.created_at), desc(ProgramWatchEvent.id))
        ).unique().all()
    )


def active_watches_for_program(session: Session, program_id: int) -> list[ProgramWatch]:
    return list(
        session.scalars(
            select(ProgramWatch)
            .where(
                ProgramWatch.program_id == program_id,
                ProgramWatch.enabled.is_(True),
            )
            .options(joinedload(ProgramWatch.profile))
            .order_by(ProgramWatch.id)
        ).all()
    )


def watch_event_exists(
    session: Session, watch_id: int, source_snapshot_id: int, event_kind: str
) -> bool:
    return session.scalar(
        select(ProgramWatchEvent.id).where(
            ProgramWatchEvent.watch_id == watch_id,
            ProgramWatchEvent.source_snapshot_id == source_snapshot_id,
            ProgramWatchEvent.event_kind == event_kind,
        )
    ) is not None


def add_watch_event(
    session: Session,
    watch: ProgramWatch,
    source_snapshot_id: int,
    event_kind: str,
    previous_value: object,
    current_value: object,
) -> None:
    if watch_event_exists(session, watch.id, source_snapshot_id, event_kind):
        return
    session.add(
        ProgramWatchEvent(
            watch_id=watch.id,
            source_snapshot_id=source_snapshot_id,
            event_kind=event_kind,
            previous_value=previous_value,
            current_value=current_value,
        )
    )
