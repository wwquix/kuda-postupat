from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from .catalog_service import CatalogNotFoundError
from .database import get_db
from .profile_models import AnonymousProfile
from .profile_schemas import (
    AnonymousProfileCreatedResponse,
    AnonymousProfileResponse,
    ProfileScoreUpdate,
    SavedAdmissionListResponse,
)
from .profile_service import (
    add_saved_program,
    add_saved_university,
    authenticate_profile,
    create_anonymous_profile,
    delete_saved_program,
    delete_saved_university,
    get_saved_admission_list,
    profile_response,
    set_profile_score,
)
from .watch_schemas import (
    ProgramWatchEventResponse,
    ProgramWatchMutationResponse,
    ProgramWatchResponse,
)
from .watch_service import (
    ProgramWatchDomainError,
    disable_program_watch,
    enable_program_watch,
    list_active_program_watches,
    list_program_watch_events,
)

router = APIRouter(prefix="/api/profile", tags=["anonymous-profile"])


def _authentication_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Требуется действующий токен анонимного профиля",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _bearer_token(authorization: Annotated[str | None, Header()] = None) -> str:
    if authorization is None or not authorization.startswith("Bearer "):
        raise _authentication_error()
    token = authorization.removeprefix("Bearer ")
    if not token or token.strip() != token or " " in token:
        raise _authentication_error()
    return token


def current_profile(
    token: Annotated[str, Depends(_bearer_token)],
    session: Annotated[Session, Depends(get_db)],
) -> AnonymousProfile:
    profile = authenticate_profile(session, token)
    if profile is None:
        raise _authentication_error()
    return profile


def _not_found(exc: CatalogNotFoundError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


def _watch_conflict(exc: ProgramWatchDomainError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.post("", response_model=AnonymousProfileCreatedResponse, status_code=status.HTTP_201_CREATED)
def create_profile(session: Annotated[Session, Depends(get_db)]) -> AnonymousProfileCreatedResponse:
    return create_anonymous_profile(session)


@router.get("", response_model=AnonymousProfileResponse)
def read_profile(
    profile: Annotated[AnonymousProfile, Depends(current_profile)],
) -> AnonymousProfileResponse:
    return profile_response(profile)


@router.patch("/score", response_model=SavedAdmissionListResponse)
def update_score(
    payload: ProfileScoreUpdate,
    profile: Annotated[AnonymousProfile, Depends(current_profile)],
    session: Annotated[Session, Depends(get_db)],
) -> SavedAdmissionListResponse:
    return set_profile_score(session, profile, payload.score)


@router.get("/saved", response_model=SavedAdmissionListResponse)
def read_saved_list(
    profile: Annotated[AnonymousProfile, Depends(current_profile)],
    session: Annotated[Session, Depends(get_db)],
) -> SavedAdmissionListResponse:
    return get_saved_admission_list(session, profile)


@router.put("/universities/{university_slug}", response_model=SavedAdmissionListResponse)
def put_university(
    university_slug: str,
    profile: Annotated[AnonymousProfile, Depends(current_profile)],
    session: Annotated[Session, Depends(get_db)],
) -> SavedAdmissionListResponse:
    try:
        return add_saved_university(session, profile, university_slug)
    except CatalogNotFoundError as exc:
        raise _not_found(exc) from exc


@router.delete("/universities/{university_slug}", response_model=SavedAdmissionListResponse)
def remove_university(
    university_slug: str,
    profile: Annotated[AnonymousProfile, Depends(current_profile)],
    session: Annotated[Session, Depends(get_db)],
) -> SavedAdmissionListResponse:
    try:
        return delete_saved_university(session, profile, university_slug)
    except CatalogNotFoundError as exc:
        raise _not_found(exc) from exc


@router.put(
    "/programs/{university_slug}/{program_slug}",
    response_model=SavedAdmissionListResponse,
)
def put_program(
    university_slug: str,
    program_slug: str,
    profile: Annotated[AnonymousProfile, Depends(current_profile)],
    session: Annotated[Session, Depends(get_db)],
) -> SavedAdmissionListResponse:
    try:
        return add_saved_program(session, profile, university_slug, program_slug)
    except CatalogNotFoundError as exc:
        raise _not_found(exc) from exc


@router.delete(
    "/programs/{university_slug}/{program_slug}",
    response_model=SavedAdmissionListResponse,
)
def remove_program(
    university_slug: str,
    program_slug: str,
    profile: Annotated[AnonymousProfile, Depends(current_profile)],
    session: Annotated[Session, Depends(get_db)],
) -> SavedAdmissionListResponse:
    try:
        return delete_saved_program(session, profile, university_slug, program_slug)
    except CatalogNotFoundError as exc:
        raise _not_found(exc) from exc


@router.get("/watches", response_model=list[ProgramWatchResponse])
def read_active_watches(
    profile: Annotated[AnonymousProfile, Depends(current_profile)],
    session: Annotated[Session, Depends(get_db)],
) -> list[ProgramWatchResponse]:
    return list_active_program_watches(session, profile)


@router.get("/watch-events", response_model=list[ProgramWatchEventResponse])
def read_watch_events(
    profile: Annotated[AnonymousProfile, Depends(current_profile)],
    session: Annotated[Session, Depends(get_db)],
) -> list[ProgramWatchEventResponse]:
    return list_program_watch_events(session, profile)


@router.put(
    "/watches/{university_slug}/{program_slug}",
    response_model=ProgramWatchResponse,
)
def put_program_watch(
    university_slug: str,
    program_slug: str,
    profile: Annotated[AnonymousProfile, Depends(current_profile)],
    session: Annotated[Session, Depends(get_db)],
) -> ProgramWatchResponse:
    try:
        return enable_program_watch(
            session, profile, university_slug, program_slug
        )
    except CatalogNotFoundError as exc:
        raise _not_found(exc) from exc
    except ProgramWatchDomainError as exc:
        raise _watch_conflict(exc) from exc


@router.delete(
    "/watches/{university_slug}/{program_slug}",
    response_model=ProgramWatchMutationResponse,
)
def remove_program_watch(
    university_slug: str,
    program_slug: str,
    profile: Annotated[AnonymousProfile, Depends(current_profile)],
    session: Annotated[Session, Depends(get_db)],
) -> ProgramWatchMutationResponse:
    try:
        return disable_program_watch(
            session, profile, university_slug, program_slug
        )
    except CatalogNotFoundError as exc:
        raise _not_found(exc) from exc
