from __future__ import annotations

import copy
import json
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.validate_university_research import validate_schema_value

ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = ROOT / "docs" / "data" / "bseu-program-import-candidates.json"
SCHEMA_PATH = ROOT / "docs" / "data" / "bseu-program-import-candidates.schema.json"
MAIN_DATABASE_PATH = ROOT / "backend" / "data" / "admission.db"


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def load_audit() -> tuple[dict[str, Any], dict[str, Any]]:
    return load_json(DATA_PATH), load_json(SCHEMA_PATH)


def numeric_source_order(candidate: dict[str, Any]) -> tuple[int, int, int]:
    identity = candidate["source_identity"]
    return (
        int(identity["specialty_id"]),
        int(identity["study_form_id"]),
        int(identity["funding_id"]),
    )


def test_candidate_json_matches_tracked_schema_and_rejects_unknown_structure() -> None:
    data, schema = load_audit()
    assert validate_schema_value(data, schema, schema, "$") == []

    missing_required = copy.deepcopy(data)
    del missing_required["source"]["structure"]
    assert validate_schema_value(missing_required, schema, schema, "$")

    unknown_field = copy.deepcopy(data)
    unknown_field["candidates"][0]["guessed_code"] = "placeholder"
    assert validate_schema_value(unknown_field, schema, schema, "$")


def test_candidates_are_deterministic_and_deduplicated() -> None:
    data, _ = load_audit()
    candidates = data["candidates"]
    summary = data["summary"]

    assert candidates == sorted(candidates, key=numeric_source_order)
    assert len({item["candidate_key"] for item in candidates}) == len(candidates) == 77

    confirmed_offering_keys = [
        item["proposed_program_offering_identity"]["match_key"]
        for item in candidates
        if item["status"] == "confirmed"
    ]
    assert None not in confirmed_offering_keys
    assert len(confirmed_offering_keys) == len(set(confirmed_offering_keys))

    status_counts = Counter(item["status"] for item in candidates)
    assert summary == {
        "source_rows": 77,
        "unique_source_specialty_ids": 23,
        "unique_normalized_program_names": 20,
        "confirmed_program_identities": 17,
        "needs_review_source_specialty_ids": 6,
        "ambiguous_normalized_program_names": 3,
        "confirmed": status_counts["confirmed"],
        "needs_review": status_counts["needs_review"],
        "unavailable": status_counts["unavailable"],
    }
    assert (summary["confirmed"], summary["needs_review"], summary["unavailable"]) == (57, 20, 0)


def test_missing_values_remain_unknown_and_name_collisions_require_review() -> None:
    data, _ = load_audit()
    candidates = data["candidates"]

    assert all(item["specialization_profile"] is None for item in candidates)
    assert {
        item["specialty_code"]
        for item in candidates
        if item["program_name"] != "Экономическая информатика"
    } == {None}
    assert all(
        item["proposed_program_identity"]["match_key"] is None
        and item["proposed_program_offering_identity"]["match_key"] is None
        for item in candidates
        if item["status"] == "needs_review"
    )

    reviewed_names = {item["program_name"] for item in candidates if item["status"] == "needs_review"}
    assert reviewed_names == {
        "Бухгалтерский учет, анализ и аудит",
        "Правоведение",
        "Экономика и управление",
    }
    assert all(item["admission_plan"] > 0 for item in candidates)


def test_economic_informatics_reuses_one_program_and_separates_offerings() -> None:
    data, _ = load_audit()
    candidates = [
        item for item in data["candidates"] if item["program_name"] == "Экономическая информатика"
    ]

    assert len(candidates) == 2
    assert {item["specialty_code"] for item in candidates} == {"6-05-0311-05"}
    assert {item["source_identity"]["specialty_id"] for item in candidates} == {"6"}
    assert {item["proposed_program_identity"]["match_key"] for item in candidates} == {
        "bseu|code|6-05-0311-05"
    }
    assert {
        (item["funding_type"], item["admission_plan"])
        for item in candidates
    } == {("budget", 25), ("paid", 60)}
    assert len({item["proposed_program_offering_identity"]["match_key"] for item in candidates}) == 2


def test_audit_validation_does_not_write_main_database() -> None:
    before = MAIN_DATABASE_PATH.stat() if MAIN_DATABASE_PATH.exists() else None
    data, schema = load_audit()
    assert validate_schema_value(data, schema, schema, "$") == []
    after = MAIN_DATABASE_PATH.stat() if MAIN_DATABASE_PATH.exists() else None

    assert before == after
