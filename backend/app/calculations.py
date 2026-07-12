from dataclasses import dataclass


@dataclass(frozen=True)
class AdmissionMetrics:
    competition: float
    cutoff_min: int | None
    cutoff_max: int | None
    applications_above_user: int | None
    estimated_user_position: int | None
    margin_min: int | None
    margin_max: int | None
    status: str
    has_competition: bool


def _parse_range(label: str) -> tuple[int, int]:
    lower, upper = label.split("-", 1)
    return int(lower), int(upper)


def calculate_metrics(
    admission_plan: int, applications_total: int, distribution: dict[str, int], user_score: int
) -> AdmissionMetrics:
    if admission_plan <= 0 or applications_total < 0 or not distribution:
        return AdmissionMetrics(0, None, None, None, None, None, None, "Недостаточно данных", False)
    competition = round(applications_total / admission_plan, 2)
    ranges = sorted(
        [(_parse_range(label), count) for label, count in distribution.items() if count > 0],
        key=lambda item: item[0][1],
        reverse=True,
    )
    above = sum(count for (lower, _upper), count in ranges if lower > user_score)
    position = above + 1
    if applications_total <= admission_plan:
        return AdmissionMetrics(competition, None, None, above, position, None, None, "Уверенно проходит", False)
    cumulative = 0
    cutoff: tuple[int, int] | None = None
    for score_range, count in ranges:
        cumulative += count
        if cumulative >= admission_plan:
            cutoff = score_range
            break
    if cutoff is None:
        return AdmissionMetrics(competition, None, None, above, position, None, None, "Недостаточно данных", True)
    cutoff_min, cutoff_max = cutoff
    margin_min, margin_max = user_score - cutoff_max, user_score - cutoff_min
    if user_score > cutoff_max:
        status = "Уверенно проходит" if margin_min >= 5 else "Пока проходит"
    elif cutoff_min <= user_score <= cutoff_max:
        status = "Пограничная ситуация"
    else:
        status = "Пока не проходит"
    return AdmissionMetrics(competition, cutoff_min, cutoff_max, above, position, margin_min, margin_max, status, True)
