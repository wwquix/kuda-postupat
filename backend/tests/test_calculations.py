from app.calculations import calculate_metrics


def test_exact_cutoff() -> None:
    result = calculate_metrics(3, 5, {"300-300": 1, "290-290": 2, "280-280": 2}, 292)
    assert (result.cutoff_min, result.cutoff_max) == (290, 290)
    assert result.status == "Пока проходит"


def test_range_cutoff_is_not_invented() -> None:
    result = calculate_metrics(3, 6, {"290-299": 1, "280-289": 1, "270-279": 3, "260-269": 1}, 276)
    assert (result.cutoff_min, result.cutoff_max) == (270, 279)
    assert result.status == "Пограничная ситуация"


def test_no_competition_when_applications_do_not_exceed_plan() -> None:
    result = calculate_metrics(10, 10, {"270-279": 10}, 200)
    assert result.has_competition is False
    assert result.cutoff_min is None
    assert result.status == "Уверенно проходит"


def test_user_statuses_and_position() -> None:
    distribution = {"290-299": 2, "280-289": 2, "270-279": 3}
    confident = calculate_metrics(4, 7, distribution, 300)
    border = calculate_metrics(4, 7, distribution, 285)
    failing = calculate_metrics(4, 7, distribution, 260)
    assert confident.status == "Уверенно проходит"
    assert border.status == "Пограничная ситуация"
    assert failing.status == "Пока не проходит"
    assert failing.estimated_user_position == 8


def test_insufficient_data() -> None:
    result = calculate_metrics(0, 4, {"270-279": 4}, 276)
    assert result.status == "Недостаточно данных"
