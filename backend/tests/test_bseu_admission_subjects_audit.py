from __future__ import annotations

import copy
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from scripts.validate_university_research import validate_schema_value

ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = ROOT / "docs" / "data" / "bseu-admission-subjects-2026.json"
SCHEMA_PATH = ROOT / "docs" / "data" / "bseu-admission-subjects-2026.schema.json"
CANDIDATES_PATH = ROOT / "docs" / "data" / "bseu-program-import-candidates.json"
MAIN_DATABASE_PATH = ROOT / "backend" / "data" / "admission.db"

NORMALIZED_KEY = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")

EXPECTED_OFFICIAL_CODES = {
    "bseu|code|6-05-0311-05": "6-05-0311-05",
    "bseu|normalized-name|бизнес-администрирование": "6-05-0412-02",
    "bseu|normalized-name|государственное управление и экономика": "6-05-0414-03",
    "bseu|normalized-name|коммерция": "6-05-0413-01",
    "bseu|normalized-name|лингвистическое обеспечение межкультурной коммуникации (с указанием языков)": "6-05-0231-03",
    "bseu|normalized-name|логистика": "6-05-0412-03",
    "bseu|normalized-name|маркетинг": "6-05-0412-04",
    "bseu|normalized-name|менеджмент": "6-05-0412-01",
    "bseu|normalized-name|мировая экономика": "6-05-0311-03",
    "bseu|normalized-name|национальная экономика": "6-05-0311-04",
    "bseu|normalized-name|политология": "6-05-0312-01",
    "bseu|normalized-name|рекламная деятельность": "6-05-0412-05",
    "bseu|normalized-name|социология": "6-05-0314-01",
    "bseu|normalized-name|статистика": "6-05-0541-01",
    "bseu|normalized-name|товароведение": "6-05-0413-02",
    "bseu|normalized-name|финансы и кредит": "6-05-0411-02",
    "bseu|normalized-name|экономика": "6-05-0311-01",
}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def load_audit() -> tuple[dict[str, Any], dict[str, Any]]:
    return load_json(DATA_PATH), load_json(SCHEMA_PATH)


def expected_programs_from_import_audit() -> dict[str, dict[str, str | None]]:
    candidates = load_json(CANDIDATES_PATH)["candidates"]
    result: dict[str, dict[str, str | None]] = {}
    for candidate in candidates:
        if candidate["status"] != "confirmed":
            continue
        identity = candidate["proposed_program_identity"]["match_key"]
        assert identity is not None
        slug = (
            "economic-informatics"
            if identity == "bseu|code|6-05-0311-05"
            else f"bseu-audit-{hashlib.sha256(identity.encode('utf-8')).hexdigest()[:20]}"
        )
        record = {
            "source_specialty_id": candidate["source_identity"]["specialty_id"],
            "slug": slug,
            "existing_code": candidate["specialty_code"],
            "imported_program_name": candidate["program_name"],
        }
        assert result.get(identity, record) == record
        result[identity] = record
    return result


def test_subject_audit_matches_schema_and_rejects_unknown_fields() -> None:
    data, schema = load_audit()
    assert validate_schema_value(data, schema, schema, "$") == []

    unknown_top_level = copy.deepcopy(data)
    unknown_top_level["guessed_minimum_score"] = 0
    assert validate_schema_value(unknown_top_level, schema, schema, "$")

    unknown_program_field = copy.deepcopy(data)
    unknown_program_field["programs"][0]["admission_probability"] = "high"
    assert validate_schema_value(unknown_program_field, schema, schema, "$")


def test_target_programs_exactly_match_confirmed_imported_identities() -> None:
    before = MAIN_DATABASE_PATH.stat() if MAIN_DATABASE_PATH.exists() else None
    data, _ = load_audit()
    expected = expected_programs_from_import_audit()
    actual = {program["program_identity"]: program for program in data["programs"]}

    assert data["university_code"] == "bseu"
    assert data["admission_year"] == 2026
    assert len(actual) == len(data["programs"]) == len(expected) == 17
    assert set(actual) == set(expected) == set(EXPECTED_OFFICIAL_CODES)
    for identity, imported in expected.items():
        assert {
            key: actual[identity][key]
            for key in ("source_specialty_id", "slug", "existing_code", "imported_program_name")
        } == imported
        assert actual[identity]["official_admission_code"] == EXPECTED_OFFICIAL_CODES[identity]

    after = MAIN_DATABASE_PATH.stat() if MAIN_DATABASE_PATH.exists() else None
    assert before == after


def test_sources_references_and_ordering_are_official_and_deterministic() -> None:
    data, _ = load_audit()
    sources = data["sources"]
    definitions = data["requirement_definitions"]
    programs = data["programs"]

    assert sources == sorted(sources, key=lambda item: item["source_id"])
    assert definitions == sorted(definitions, key=lambda item: item["definition_id"])
    assert programs == sorted(programs, key=lambda item: item["program_identity"])

    source_ids = {source["source_id"] for source in sources}
    assert len(source_ids) == len(sources)
    allowed_domains = set(data["source_policy"]["allowed_domains"])
    for source in sources:
        hostname = urlparse(source["url"]).hostname
        assert hostname in allowed_domains

    definition_ids = {definition["definition_id"] for definition in definitions}
    assert len(definition_ids) == len(definitions)
    for definition in definitions:
        assert definition["source_ids"] == sorted(definition["source_ids"])
        assert set(definition["source_ids"]) <= source_ids

    requirement_ids: list[str] = []
    for program in programs:
        assert program["source_ids"] == sorted(program["source_ids"])
        assert set(program["source_ids"]) <= source_ids
        sets = program["requirement_sets"]
        assert sets == sorted(sets, key=lambda item: item["requirement_set_id"])
        for requirement_set in sets:
            requirement_ids.append(requirement_set["requirement_set_id"])
            assert requirement_set["admission_year"] == 2026
            assert requirement_set["requirement_definition_id"] in definition_ids
            assert requirement_set["source_ids"] == sorted(requirement_set["source_ids"])
            assert set(requirement_set["source_ids"]) <= source_ids
    assert len(requirement_ids) == len(set(requirement_ids)) == 37


def test_subject_groups_model_choices_without_empty_or_guessed_values() -> None:
    data, _ = load_audit()
    definitions = {item["definition_id"]: item for item in data["requirement_definitions"]}

    for definition in definitions.values():
        groups = definition["subject_groups"]
        assert [group["position"] for group in groups] == list(range(1, len(groups) + 1))
        assert len({group["group_key"] for group in groups}) == len(groups)
        for group in groups:
            subjects = group["allowed_subjects"]
            assert 1 <= group["choose_count"] <= len(subjects)
            assert subjects == sorted(subjects, key=lambda item: item["subject_key"])
            assert all(NORMALIZED_KEY.fullmatch(item["subject_key"]) for item in subjects)
            assert all(item["official_label_ru"].strip() for item in subjects)
            assert all(item["official_label_be"] is None for item in subjects)

    math_full = definitions["full-math-foreign-centralized"]["subject_groups"]
    assert math_full[0]["choose_count"] == 1
    assert [item["subject_key"] for item in math_full[0]["allowed_subjects"]] == [
        "belarusian_language",
        "russian_language",
    ]
    social_history = definitions["full-social-history-centralized"]["subject_groups"][-1]
    assert social_history["choose_count"] == 1
    assert [item["subject_key"] for item in social_history["allowed_subjects"]] == [
        "history_belarus",
        "history_belarus_world_context",
    ]


def test_pathways_statuses_and_summary_match_actual_records() -> None:
    data, _ = load_audit()
    programs = data["programs"]
    requirement_sets = [item for program in programs for item in program["requirement_sets"]]
    status_counts = Counter(program["status"] for program in programs)
    pathway_counts = Counter(
        (item["study_form"], item["track"], item["admission_pathway"])
        for item in requirement_sets
    )
    definition_counts = Counter(item["requirement_definition_id"] for item in requirement_sets)

    assert all(program["requirement_sets"] for program in programs if program["status"] == "confirmed")
    assert all(program["review_reason"] is None for program in programs if program["status"] == "confirmed")
    assert all(
        program["review_reason"]
        for program in programs
        if program["status"] in {"needs_review", "unavailable"}
    )
    assert pathway_counts == {
        ("full_time", "full", "general_competition"): 17,
        ("full_time", "full", "targeted_training"): 6,
        ("part_time", "full", "general_competition"): 7,
        ("part_time", "shortened", "general_competition"): 7,
    }
    assert definition_counts == {
        "full-foreign-history-centralized": 1,
        "full-math-foreign-centralized": 21,
        "full-social-history-centralized": 2,
        "shortened-economics-accounting-written": 1,
        "shortened-economics-it-written": 1,
        "shortened-economics-management-written": 5,
        "targeted-math-oral": 4,
        "targeted-social-oral": 2,
    }
    assert data["summary"] == {
        "target_programs": len(programs),
        "confirmed": status_counts["confirmed"],
        "needs_review": status_counts["needs_review"],
        "unavailable": status_counts["unavailable"],
        "requirement_sets": len(requirement_sets),
        "requirement_definitions": len(data["requirement_definitions"]),
        "official_sources": len(data["sources"]),
    }
    assert data["summary"] == {
        "target_programs": 17,
        "confirmed": 17,
        "needs_review": 0,
        "unavailable": 0,
        "requirement_sets": 37,
        "requirement_definitions": 8,
        "official_sources": 3,
    }
    assert data["review_items"] == []
