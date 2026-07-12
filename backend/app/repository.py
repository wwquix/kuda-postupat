import hashlib
import json
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from .calculations import AdmissionMetrics
from .models import AdmissionSnapshot, Specialty
from .parser import ParsedSpecialty, normalize_text


def normalized_snapshot_hash(row: ParsedSpecialty, user_score: int, metrics: AdmissionMetrics) -> str:
    payload = {
        "plan": row.admission_plan,
        "total": row.applications_total,
        "distribution": sorted(row.distribution.items()),
        "user_score": user_score,
        "cutoff": [metrics.cutoff_min, metrics.cutoff_max],
        "position": metrics.estimated_user_position,
        "status": metrics.status,
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def get_or_create_specialty(session: Session, row: ParsedSpecialty, source_url: str) -> Specialty:
    normalized = normalize_text(row.display_name)
    specialty = session.scalar(
        select(Specialty).where(
            Specialty.normalized_name == normalized,
            Specialty.study_form == row.study_form,
            Specialty.funding_type == row.funding_type,
        )
    )
    if specialty is None:
        specialty = Specialty(
            normalized_name=normalized,
            display_name=row.display_name,
            study_form=row.study_form,
            funding_type=row.funding_type,
            source_url=source_url,
            active=True,
        )
        session.add(specialty)
        session.flush()
    else:
        specialty.display_name = row.display_name
        specialty.source_url = source_url
        specialty.active = True
    return specialty


def latest_snapshot(session: Session, specialty_id: int) -> AdmissionSnapshot | None:
    return session.scalar(
        select(AdmissionSnapshot)
        .where(AdmissionSnapshot.specialty_id == specialty_id)
        .order_by(desc(AdmissionSnapshot.fetched_at))
        .limit(1)
    )


def save_snapshot_if_changed(
    session: Session,
    specialty: Specialty,
    row: ParsedSpecialty,
    user_score: int,
    metrics: AdmissionMetrics,
) -> tuple[AdmissionSnapshot, AdmissionSnapshot | None, bool]:
    previous = latest_snapshot(session, specialty.id)
    data_hash = normalized_snapshot_hash(row, user_score, metrics)
    if previous and previous.raw_data_hash == data_hash:
        return previous, previous, False
    snapshot = AdmissionSnapshot(
        specialty_id=specialty.id,
        fetched_at=datetime.now(UTC),
        source_updated_at=row.source_updated_at,
        admission_plan=row.admission_plan,
        applications_total=row.applications_total,
        competition=metrics.competition,
        estimated_cutoff_min=metrics.cutoff_min,
        estimated_cutoff_max=metrics.cutoff_max,
        user_score=user_score,
        estimated_user_position=metrics.estimated_user_position,
        user_status=metrics.status,
        distribution_json=json.dumps(row.distribution, ensure_ascii=False, sort_keys=True),
        raw_data_hash=data_hash,
    )
    session.add(snapshot)
    session.flush()
    return snapshot, previous, True


def snapshot_to_dict(snapshot: AdmissionSnapshot, specialty: Specialty) -> dict:
    distribution = json.loads(snapshot.distribution_json)
    cutoff = None
    if snapshot.estimated_cutoff_min is not None:
        cutoff = (
            str(snapshot.estimated_cutoff_min)
            if snapshot.estimated_cutoff_min == snapshot.estimated_cutoff_max
            else f"{snapshot.estimated_cutoff_min}–{snapshot.estimated_cutoff_max}"
        )
    fetched_at = snapshot.fetched_at.replace(tzinfo=UTC) if snapshot.fetched_at.tzinfo is None else snapshot.fetched_at
    source_updated_at = snapshot.source_updated_at
    if source_updated_at and source_updated_at.tzinfo is None:
        source_updated_at = source_updated_at.replace(tzinfo=ZoneInfo("Europe/Minsk"))
    return {
        "id": snapshot.id,
        "specialty_id": specialty.id,
        "specialty": specialty.display_name,
        "study_form": specialty.study_form,
        "funding_type": specialty.funding_type,
        "source_url": specialty.source_url,
        "fetched_at": fetched_at,
        "source_updated_at": source_updated_at,
        "admission_plan": snapshot.admission_plan,
        "applications_total": snapshot.applications_total,
        "competition": snapshot.competition,
        "estimated_cutoff_min": snapshot.estimated_cutoff_min,
        "estimated_cutoff_max": snapshot.estimated_cutoff_max,
        "estimated_cutoff": cutoff,
        "no_competition": snapshot.applications_total <= snapshot.admission_plan,
        "user_score": snapshot.user_score,
        "estimated_user_position": snapshot.estimated_user_position,
        "user_status": snapshot.user_status,
        "distribution": distribution,
    }
