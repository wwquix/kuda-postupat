from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.calculations import calculate_metrics
from app.models import Base
from app.parser import ParsedSpecialty
from app.repository import get_or_create_specialty, save_snapshot_if_changed


def test_identical_snapshot_is_not_duplicated() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    row = ParsedSpecialty("Экономическая информатика", "дневная", "платная", 3, 5, {"270-279": 5}, datetime.now())
    metrics = calculate_metrics(3, 5, row.distribution, 276)
    with Session(engine) as session:
        specialty = get_or_create_specialty(session, row, "https://example.test")
        first, _, first_created = save_snapshot_if_changed(session, specialty, row, 276, metrics)
        session.commit()
        second, _, second_created = save_snapshot_if_changed(session, specialty, row, 276, metrics)
        assert first_created is True
        assert second_created is False
        assert first.id == second.id
