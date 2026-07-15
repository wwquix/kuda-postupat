from sqlalchemy.orm import Session

from .catalog_models import FundingType, InstitutionKind, OwnershipType, StudyForm
from .catalog_repository import ProgramRow, UniversityRow, catalog_counts
from .catalog_search import normalize_search_text
from .catalog_service import (
    _coverage_response,
    _pagination,
    _program_response,
    _university_list_item,
)
from .profile_service import program_monitoring_for_score
from .recommendation_repository import (
    RecommendationFilters,
    recommendation_program_rows,
    recommendation_university_rows,
)
from .recommendation_schemas import (
    ProgramRecommendationCollection,
    ProgramRecommendationResponse,
    RecommendationReasonResponse,
    RecommendationResponse,
    RecommendationResultClass,
    UniversityRecommendationCollection,
    UniversityRecommendationResponse,
)

INSUFFICIENT_DATA_TEXT = "Недостаточно данных для оценки поступления"
PARAMETER_MATCH_TEXT = "Совпадает с выбранными параметрами"
RESULT_LABELS = {
    RecommendationResultClass.MONITORED_STATUS: "Статус рассчитан по данным мониторинга",
    RecommendationResultClass.PARAMETER_MATCH: PARAMETER_MATCH_TEXT,
    RecommendationResultClass.INSUFFICIENT_COVERAGE: "Недостаточно импортированных данных",
}
RESULT_CLASS_ORDER = {
    RecommendationResultClass.MONITORED_STATUS: 0,
    RecommendationResultClass.PARAMETER_MATCH: 1,
    RecommendationResultClass.INSUFFICIENT_COVERAGE: 2,
}


def _applied_parameters(
    *,
    score: int | None,
    city: str | None,
    region: str | None,
    ownership_type: OwnershipType | None,
    institution_kind: InstitutionKind | None,
    category: str | None,
    study_form: StudyForm | None,
    funding_type: FundingType | None,
    online_monitoring: bool | None,
) -> list[RecommendationReasonResponse]:
    values: list[tuple[str, object | None]] = [
        ("score", score),
        ("city", city),
        ("region", region),
        ("ownership_type", ownership_type.value if ownership_type else None),
        ("institution_kind", institution_kind.value if institution_kind else None),
        ("category", category),
        ("study_form", study_form.value if study_form else None),
        ("funding_type", funding_type.value if funding_type else None),
        (
            "online_monitoring",
            str(online_monitoring).lower() if online_monitoring is not None else None,
        ),
    ]
    return [
        RecommendationReasonResponse(parameter=parameter, value=str(value))
        for parameter, value in values
        if value is not None
    ]


def _match_reasons(
    applied: list[RecommendationReasonResponse], *, item_kind: str
) -> list[RecommendationReasonResponse]:
    reasons = [item for item in applied if item.parameter != "score"]
    if reasons:
        return reasons
    return [
        RecommendationReasonResponse(
            parameter="catalog",
            value="imported_program" if item_kind == "program" else "active_university",
        )
    ]


def _program_coverage_notes(
    row: ProgramRow, monitoring_state: str
) -> list[str]:
    notes: list[str] = []
    if row.offering_count == 0:
        notes.append(
            "Варианты обучения для этой программы ещё не импортированы платформой; "
            "это не означает, что их нет в вузе."
        )
    if monitoring_state == "score_required":
        notes.append("Для расчёта статуса нужно явно указать балл.")
    elif monitoring_state == "temporarily_unavailable":
        notes.append("Текущие данные мониторинга отсутствуют или устарели.")
    elif monitoring_state == "unsupported":
        notes.append("Для этой программы расчёт статуса поступления пока не поддерживается.")
    return notes


def _program_result(
    session: Session,
    row: ProgramRow,
    *,
    score: int | None,
    stale_after_minutes: int,
    applied: list[RecommendationReasonResponse],
) -> ProgramRecommendationResponse:
    monitoring_state, monitoring = program_monitoring_for_score(
        session,
        row.program,
        score,
        stale_after_minutes=stale_after_minutes,
    )
    if monitoring_state == "available" and monitoring is not None:
        result_class = RecommendationResultClass.MONITORED_STATUS
        admission_evaluation = monitoring.status
    elif row.offering_count == 0:
        result_class = RecommendationResultClass.INSUFFICIENT_COVERAGE
        admission_evaluation = INSUFFICIENT_DATA_TEXT
    else:
        result_class = RecommendationResultClass.PARAMETER_MATCH
        admission_evaluation = INSUFFICIENT_DATA_TEXT
    reasons = _match_reasons(applied, item_kind="program")
    if monitoring is not None and score is not None:
        reasons = [
            *reasons,
            RecommendationReasonResponse(parameter="score", value=str(score)),
        ]
    return ProgramRecommendationResponse(
        result_class=result_class,
        result_label=RESULT_LABELS[result_class],
        admission_evaluation=admission_evaluation,
        match_reasons=reasons,
        coverage_notes=_program_coverage_notes(row, monitoring_state),
        monitoring_state=monitoring_state,
        monitoring=monitoring,
        program=_program_response(row),
    )


def _university_result(
    row: UniversityRow,
    *,
    applied: list[RecommendationReasonResponse],
) -> UniversityRecommendationResponse:
    notes: list[str] = []
    if row.program_count == 0:
        notes.append(
            "Программы этого вуза ещё не импортированы платформой; "
            "это не означает, что у вуза нет реальных программ."
        )
    elif row.offering_count == 0:
        notes.append(
            "Варианты обучения для импортированных программ ещё не добавлены платформой."
        )
    result_class = (
        RecommendationResultClass.INSUFFICIENT_COVERAGE
        if row.program_count == 0 or row.offering_count == 0
        else RecommendationResultClass.PARAMETER_MATCH
    )
    return UniversityRecommendationResponse(
        result_class=result_class,
        result_label=RESULT_LABELS[result_class],
        admission_evaluation=INSUFFICIENT_DATA_TEXT,
        match_reasons=_match_reasons(applied, item_kind="university"),
        coverage_notes=notes,
        university=_university_list_item(row),
    )


def _reason_count(reasons: list[RecommendationReasonResponse]) -> int:
    return sum(item.parameter not in {"catalog", "score"} for item in reasons)


def _program_sort_key(item: ProgramRecommendationResponse) -> tuple:
    return (
        RESULT_CLASS_ORDER[item.result_class],
        -_reason_count(item.match_reasons),
        -item.program.offering_count,
        normalize_search_text(item.program.university.short_name),
        normalize_search_text(item.program.name),
        item.program.id,
    )


def _university_sort_key(item: UniversityRecommendationResponse) -> tuple:
    return (
        RESULT_CLASS_ORDER[item.result_class],
        -_reason_count(item.match_reasons),
        -item.university.program_count,
        -item.university.offering_count,
        normalize_search_text(item.university.full_name),
        item.university.id,
    )


def _page(items: list, page: int, page_size: int) -> list:  # type: ignore[type-arg]
    start = (page - 1) * page_size
    return items[start : start + page_size]


def get_recommendations(
    session: Session,
    *,
    score: int | None,
    city: str | None,
    region: str | None,
    ownership_type: OwnershipType | None,
    institution_kind: InstitutionKind | None,
    category: str | None,
    study_form: StudyForm | None,
    funding_type: FundingType | None,
    online_monitoring: bool | None,
    page: int,
    page_size: int,
    stale_after_minutes: int,
) -> RecommendationResponse:
    normalized_city = normalize_search_text(city) or None
    normalized_region = normalize_search_text(region) or None
    normalized_category = normalize_search_text(category) or None
    filters = RecommendationFilters(
        city=normalized_city,
        region=normalized_region,
        ownership_type=ownership_type,
        institution_kind=institution_kind,
        category=normalized_category,
        study_form=study_form,
        funding_type=funding_type,
        online_monitoring=online_monitoring,
    )
    applied = _applied_parameters(
        score=score,
        city=city,
        region=region,
        ownership_type=ownership_type,
        institution_kind=institution_kind,
        category=category,
        study_form=study_form,
        funding_type=funding_type,
        online_monitoring=online_monitoring,
    )
    programs = sorted(
        (
            _program_result(
                session,
                row,
                score=score,
                stale_after_minutes=stale_after_minutes,
                applied=applied,
            )
            for row in recommendation_program_rows(session, filters)
        ),
        key=_program_sort_key,
    )
    universities = sorted(
        (
            _university_result(row, applied=applied)
            for row in recommendation_university_rows(session, filters)
        ),
        key=_university_sort_key,
    )
    counts = catalog_counts(session)
    return RecommendationResponse(
        applied_parameters=applied,
        programs=ProgramRecommendationCollection(
            items=_page(programs, page, page_size),
            pagination=_pagination(page, page_size, len(programs)),
        ),
        universities=UniversityRecommendationCollection(
            items=_page(universities, page, page_size),
            pagination=_pagination(page, page_size, len(universities)),
        ),
        coverage=_coverage_response(counts),
    )
