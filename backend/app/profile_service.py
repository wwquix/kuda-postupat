from sqlalchemy.orm import Session

from .calculations import calculate_metrics
from .catalog_models import MonitoringStatus, Program, University
from .catalog_repository import program_by_university_and_slug, university_by_slug
from .catalog_service import (
    CatalogNotFoundError,
    get_program,
    get_university,
    offering_latest,
)
from .config import get_settings
from .profile_models import AnonymousProfile
from .profile_repository import (
    create_profile_record,
    profile_by_token,
    remove_program,
    remove_university,
    save_program,
    save_university,
    saved_program_rows,
    saved_university_rows,
    update_personal_score,
)
from .profile_schemas import (
    AnonymousProfileCreatedResponse,
    AnonymousProfileResponse,
    PersonalAdmissionStatusResponse,
    SavedAdmissionListResponse,
    SavedProgramResponse,
    SavedUniversityResponse,
)
from .profile_security import generate_profile_token, hash_profile_token


def create_anonymous_profile(session: Session) -> AnonymousProfileCreatedResponse:
    token = generate_profile_token()
    profile = create_profile_record(session, hash_profile_token(token))
    saved = get_saved_admission_list(session, profile)
    return AnonymousProfileCreatedResponse(token=token, **saved.model_dump())


def authenticate_profile(session: Session, token: str) -> AnonymousProfile | None:
    return profile_by_token(session, token)


def profile_response(profile: AnonymousProfile) -> AnonymousProfileResponse:
    return AnonymousProfileResponse.model_validate(profile)


def set_profile_score(
    session: Session, profile: AnonymousProfile, score: int | None
) -> SavedAdmissionListResponse:
    update_personal_score(session, profile, score)
    return get_saved_admission_list(session, profile)


def _resolve_university(session: Session, slug: str) -> University:
    university = university_by_slug(session, slug)
    if university is None:
        raise CatalogNotFoundError("Университет не найден")
    return university


def _resolve_program(session: Session, university_slug: str, program_slug: str) -> Program:
    university = _resolve_university(session, university_slug)
    row = program_by_university_and_slug(session, university.id, program_slug)
    if row is None:
        raise CatalogNotFoundError("Программа не найдена")
    return row.program


def add_saved_university(
    session: Session, profile: AnonymousProfile, slug: str
) -> SavedAdmissionListResponse:
    save_university(session, profile, _resolve_university(session, slug))
    return get_saved_admission_list(session, profile)


def delete_saved_university(
    session: Session, profile: AnonymousProfile, slug: str
) -> SavedAdmissionListResponse:
    remove_university(session, profile, _resolve_university(session, slug))
    return get_saved_admission_list(session, profile)


def add_saved_program(
    session: Session,
    profile: AnonymousProfile,
    university_slug: str,
    program_slug: str,
) -> SavedAdmissionListResponse:
    save_program(session, profile, _resolve_program(session, university_slug, program_slug))
    return get_saved_admission_list(session, profile)


def delete_saved_program(
    session: Session,
    profile: AnonymousProfile,
    university_slug: str,
    program_slug: str,
) -> SavedAdmissionListResponse:
    remove_program(session, profile, _resolve_program(session, university_slug, program_slug))
    return get_saved_admission_list(session, profile)


def _program_monitoring(
    session: Session, profile: AnonymousProfile, program: Program
) -> tuple[str, PersonalAdmissionStatusResponse | None]:
    monitored_offerings = sorted(
        (
            offering
            for offering in program.offerings
            if offering.monitoring_supported
            and offering.monitoring_status == MonitoringStatus.ONLINE
        ),
        key=lambda offering: (-offering.admission_year, offering.id),
    )
    if not monitored_offerings:
        return "unsupported", None
    if profile.personal_score is None:
        return "score_required", None
    offering = monitored_offerings[0]
    try:
        snapshot = offering_latest(
            session,
            offering.id,
            stale_after_minutes=get_settings().stale_after_minutes,
        )
        if snapshot.is_stale:
            return "temporarily_unavailable", None
        metrics = calculate_metrics(
            snapshot.admission_plan,
            snapshot.applications_total,
            snapshot.distribution,
            profile.personal_score,
        )
    except Exception:
        return "temporarily_unavailable", None
    if metrics.status == "Недостаточно данных":
        return "temporarily_unavailable", None
    return "available", PersonalAdmissionStatusResponse(
        offering_id=offering.id,
        snapshot_id=snapshot.id,
        fetched_at=snapshot.fetched_at,
        status=metrics.status,
        competition=metrics.competition,
        estimated_cutoff_min=metrics.cutoff_min,
        estimated_cutoff_max=metrics.cutoff_max,
        estimated_user_position=metrics.estimated_user_position,
        margin_min=metrics.margin_min,
        margin_max=metrics.margin_max,
        has_competition=metrics.has_competition,
    )


def get_saved_admission_list(
    session: Session, profile: AnonymousProfile
) -> SavedAdmissionListResponse:
    universities = [
        SavedUniversityResponse(
            saved_at=link.created_at,
            university=get_university(session, university.slug),
        )
        for link, university in saved_university_rows(session, profile.id)
    ]
    programs: list[SavedProgramResponse] = []
    for link, program in saved_program_rows(session, profile.id):
        program_response = get_program(session, program.id)
        monitoring_state, monitoring = _program_monitoring(session, profile, program)
        programs.append(
            SavedProgramResponse(
                saved_at=link.created_at,
                program=program_response,
                monitoring_state=monitoring_state,
                monitoring=monitoring,
            )
        )
    return SavedAdmissionListResponse(
        profile=profile_response(profile),
        universities=universities,
        programs=programs,
    )
