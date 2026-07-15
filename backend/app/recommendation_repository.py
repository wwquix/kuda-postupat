from dataclasses import dataclass

from sqlalchemy import exists, select
from sqlalchemy.orm import Session, joinedload, selectinload

from .catalog_models import (
    FundingType,
    InstitutionKind,
    OwnershipType,
    Program,
    ProgramOffering,
    StudyForm,
    University,
)
from .catalog_repository import (
    ProgramRow,
    UniversityQuery,
    UniversityRow,
    _online_adapter_exists,
    _program_offering_count,
    _university_offering_count,
    _university_predicates,
    _university_program_count,
)


@dataclass(frozen=True)
class RecommendationFilters:
    city: str | None = None
    region: str | None = None
    ownership_type: OwnershipType | None = None
    institution_kind: InstitutionKind | None = None
    category: str | None = None
    study_form: StudyForm | None = None
    funding_type: FundingType | None = None
    online_monitoring: bool | None = None


def _university_query(filters: RecommendationFilters) -> UniversityQuery:
    return UniversityQuery(
        city=filters.city,
        region=filters.region,
        ownership_type=filters.ownership_type,
        institution_kind=filters.institution_kind,
        category=filters.category,
        online_monitoring=filters.online_monitoring,
        active=True,
    )


def _offering_conditions(filters: RecommendationFilters) -> list:  # type: ignore[type-arg]
    conditions = []
    if filters.study_form is not None:
        conditions.append(ProgramOffering.study_form == filters.study_form)
    if filters.funding_type is not None:
        conditions.append(ProgramOffering.funding_type == filters.funding_type)
    return conditions


def recommendation_program_rows(
    session: Session, filters: RecommendationFilters
) -> list[ProgramRow]:
    offering_count = _program_offering_count()
    predicates = _university_predicates(_university_query(filters))
    offering_conditions = _offering_conditions(filters)
    if offering_conditions:
        predicates.append(
            exists(
                select(ProgramOffering.id).where(
                    ProgramOffering.program_id == Program.id,
                    *offering_conditions,
                )
            )
        )
    rows = session.execute(
        select(Program, offering_count.label("offering_count"))
        .join(University)
        .where(Program.active.is_(True), *predicates)
        .options(joinedload(Program.university), selectinload(Program.offerings))
        .order_by(Program.id)
    ).all()
    return [ProgramRow(program=row[0], offering_count=int(row[1])) for row in rows]


def recommendation_university_rows(
    session: Session, filters: RecommendationFilters
) -> list[UniversityRow]:
    program_count = _university_program_count()
    offering_count = _university_offering_count()
    adapter_exists = _online_adapter_exists()
    predicates = _university_predicates(_university_query(filters))
    offering_conditions = _offering_conditions(filters)
    if offering_conditions:
        predicates.append(
            exists(
                select(ProgramOffering.id)
                .join(Program, Program.id == ProgramOffering.program_id)
                .where(
                    Program.university_id == University.id,
                    Program.active.is_(True),
                    *offering_conditions,
                )
            )
        )
    rows = session.execute(
        select(
            University,
            program_count.label("program_count"),
            offering_count.label("offering_count"),
            adapter_exists.label("has_online_adapter"),
        )
        .where(*predicates)
        .options(selectinload(University.categories))
        .order_by(University.id)
    ).all()
    return [
        UniversityRow(
            university=row[0],
            program_count=int(row[1]),
            offering_count=int(row[2]),
            has_online_adapter=bool(row[3]),
        )
        for row in rows
    ]
