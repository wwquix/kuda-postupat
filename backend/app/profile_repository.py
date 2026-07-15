from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .catalog_models import Program, University, utc_now
from .profile_models import AnonymousProfile, SavedProgram, SavedUniversity
from .profile_security import hash_profile_token


def profile_by_token(session: Session, token: str) -> AnonymousProfile | None:
    return session.scalar(
        select(AnonymousProfile).where(AnonymousProfile.token_hash == hash_profile_token(token))
    )


def create_profile_record(session: Session, token_hash: str) -> AnonymousProfile:
    profile = AnonymousProfile(token_hash=token_hash)
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


def update_personal_score(
    session: Session, profile: AnonymousProfile, score: int | None
) -> AnonymousProfile:
    profile.personal_score = score
    profile.updated_at = utc_now()
    session.commit()
    session.refresh(profile)
    return profile


def save_university(
    session: Session, profile: AnonymousProfile, university: University
) -> None:
    key = (profile.id, university.id)
    if session.get(SavedUniversity, key) is None:
        session.add(SavedUniversity(profile_id=profile.id, university_id=university.id))
        profile.updated_at = utc_now()
        session.commit()


def remove_university(
    session: Session, profile: AnonymousProfile, university: University
) -> None:
    result = session.execute(
        delete(SavedUniversity).where(
            SavedUniversity.profile_id == profile.id,
            SavedUniversity.university_id == university.id,
        )
    )
    if result.rowcount:
        profile.updated_at = utc_now()
    session.commit()


def save_program(session: Session, profile: AnonymousProfile, program: Program) -> None:
    key = (profile.id, program.id)
    if session.get(SavedProgram, key) is None:
        session.add(SavedProgram(profile_id=profile.id, program_id=program.id))
        profile.updated_at = utc_now()
        session.commit()


def remove_program(session: Session, profile: AnonymousProfile, program: Program) -> None:
    result = session.execute(
        delete(SavedProgram).where(
            SavedProgram.profile_id == profile.id,
            SavedProgram.program_id == program.id,
        )
    )
    if result.rowcount:
        profile.updated_at = utc_now()
    session.commit()


def saved_university_rows(
    session: Session, profile_id: int
) -> list[tuple[SavedUniversity, University]]:
    return list(
        session.execute(
            select(SavedUniversity, University)
            .join(University, University.id == SavedUniversity.university_id)
            .where(SavedUniversity.profile_id == profile_id, University.active.is_(True))
            .order_by(func.catalog_normalize(University.full_name), University.id)
        ).all()
    )


def saved_program_rows(
    session: Session, profile_id: int
) -> list[tuple[SavedProgram, Program]]:
    return list(
        session.execute(
            select(SavedProgram, Program)
            .join(Program, Program.id == SavedProgram.program_id)
            .join(University, University.id == Program.university_id)
            .where(
                SavedProgram.profile_id == profile_id,
                Program.active.is_(True),
                University.active.is_(True),
            )
            .order_by(
                func.catalog_normalize(University.full_name),
                func.catalog_normalize(Program.name),
                Program.id,
            )
        ).all()
    )
