from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session, selectinload

from .catalog_models import (
    DataSource,
    Program,
    ProgramOffering,
    University,
    UniversityCategory,
    UniversityCategoryLink,
)


@dataclass(frozen=True)
class CatalogSummary:
    universities_total: int
    ownership_totals: dict[str, int]
    cities_total: int
    monitoring_totals: dict[str, int]
    with_admissions_url: int
    categories_total: int
    category_links_total: int
    data_sources_total: int
    programs_total: int
    offerings_total: int

    def as_dict(self) -> dict[str, object]:
        return {
            "universities_total": self.universities_total,
            "ownership_totals": self.ownership_totals,
            "cities_total": self.cities_total,
            "monitoring_totals": self.monitoring_totals,
            "with_admissions_url": self.with_admissions_url,
            "categories_total": self.categories_total,
            "category_links_total": self.category_links_total,
            "data_sources_total": self.data_sources_total,
            "programs_total": self.programs_total,
            "offerings_total": self.offerings_total,
        }


def list_universities_for_import(session: Session) -> list[University]:
    return list(
        session.scalars(
            select(University)
            .options(
                selectinload(University.categories),
                selectinload(University.data_sources),
            )
            .order_by(University.code)
        ).all()
    )


def list_categories(session: Session) -> list[UniversityCategory]:
    return list(session.scalars(select(UniversityCategory).order_by(UniversityCategory.code)).all())


def list_data_sources(session: Session) -> list[DataSource]:
    return list(session.scalars(select(DataSource).order_by(DataSource.id)).all())


def get_university_for_export(session: Session, slug: str) -> University | None:
    return session.scalar(
        select(University)
        .where(University.slug == slug)
        .options(
            selectinload(University.categories),
            selectinload(University.data_sources),
            selectinload(University.programs).selectinload(Program.offerings),
        )
    )


def add_university(session: Session, university: University) -> None:
    session.add(university)


def add_category(session: Session, category: UniversityCategory) -> None:
    session.add(category)


def add_category_link(session: Session, link: UniversityCategoryLink) -> None:
    session.add(link)


def add_data_source(session: Session, source: DataSource) -> None:
    session.add(source)


def duplicate_values(session: Session, column) -> list[str]:  # type: ignore[no-untyped-def]
    statement = select(column).group_by(column).having(func.count() > 1).order_by(column)
    return [str(value) for value in session.scalars(statement).all()]


def duplicate_category_links(session: Session) -> list[str]:
    rows = session.execute(
        select(UniversityCategoryLink.university_id, UniversityCategoryLink.category_id)
        .group_by(UniversityCategoryLink.university_id, UniversityCategoryLink.category_id)
        .having(func.count() > 1)
    ).all()
    return [f"{university_id}:{category_id}" for university_id, category_id in rows]


def duplicate_data_sources(session: Session) -> list[str]:
    rows = session.execute(
        select(DataSource.university_id, DataSource.source_type, DataSource.source_url)
        .group_by(DataSource.university_id, DataSource.source_type, DataSource.source_url)
        .having(func.count() > 1)
    ).all()
    return [f"{university_id}:{source_type}:{source_url}" for university_id, source_type, source_url in rows]


def catalog_summary(session: Session) -> CatalogSummary:
    ownership_totals = {
        str(value.value if hasattr(value, "value") else value): count
        for value, count in session.execute(
            select(University.ownership_type, func.count()).group_by(University.ownership_type)
        )
    }
    monitoring_totals = {
        str(value.value if hasattr(value, "value") else value): count
        for value, count in session.execute(
            select(University.monitoring_status, func.count()).group_by(University.monitoring_status)
        )
    }
    return CatalogSummary(
        universities_total=session.scalar(select(func.count()).select_from(University)) or 0,
        ownership_totals=ownership_totals,
        cities_total=session.scalar(select(func.count(distinct(University.city))).where(University.city.is_not(None)))
        or 0,
        monitoring_totals=monitoring_totals,
        with_admissions_url=session.scalar(
            select(func.count()).select_from(University).where(University.admissions_url.is_not(None))
        )
        or 0,
        categories_total=session.scalar(select(func.count()).select_from(UniversityCategory)) or 0,
        category_links_total=session.scalar(select(func.count()).select_from(UniversityCategoryLink)) or 0,
        data_sources_total=session.scalar(select(func.count()).select_from(DataSource)) or 0,
        programs_total=session.scalar(select(func.count()).select_from(Program)) or 0,
        offerings_total=session.scalar(select(func.count()).select_from(ProgramOffering)) or 0,
    )
