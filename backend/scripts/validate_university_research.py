from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = ROOT / "backend" / "data" / "research" / "universities-canonical-2026.json"
SCHEMA_PATH = ROOT / "backend" / "data" / "research" / "universities-canonical.schema.json"
PLACEHOLDER_HOSTS = {"example.com", "example.org", "example.invalid", "localhost", "127.0.0.1"}


class ValidationFailure(Exception):
    pass


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationFailure(f"Cannot load {path}: {exc}") from exc


def resolve_ref(root_schema: dict[str, Any], ref: str) -> dict[str, Any]:
    if not ref.startswith("#/"):
        raise ValidationFailure(f"Only local schema references are supported: {ref}")
    value: Any = root_schema
    for part in ref[2:].split("/"):
        value = value[part.replace("~1", "/").replace("~0", "~")]
    if not isinstance(value, dict):
        raise ValidationFailure(f"Schema reference does not resolve to an object: {ref}")
    return value


def is_type(value: Any, expected: str) -> bool:
    return {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "null": value is None,
    }.get(expected, False)


def valid_format(value: str, format_name: str) -> bool:
    try:
        if format_name == "uri":
            parsed = urlparse(value)
            return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
        if format_name == "date-time":
            datetime.fromisoformat(value.replace("Z", "+00:00"))
            return "T" in value
        if format_name == "date":
            date.fromisoformat(value)
            return True
    except ValueError:
        return False
    return True


def validate_schema_value(
    value: Any,
    schema: dict[str, Any],
    root_schema: dict[str, Any],
    path: str,
) -> list[str]:
    if "$ref" in schema:
        return validate_schema_value(value, resolve_ref(root_schema, schema["$ref"]), root_schema, path)
    if "oneOf" in schema:
        matches = [
            branch
            for branch in schema["oneOf"]
            if not validate_schema_value(value, branch, root_schema, path)
        ]
        return [] if len(matches) == 1 else [f"{path}: expected exactly one oneOf branch, got {len(matches)}"]

    errors: list[str] = []
    expected_type = schema.get("type")
    if expected_type and not is_type(value, expected_type):
        return [f"{path}: expected {expected_type}, got {type(value).__name__}"]
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: expected constant {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: value {value!r} is outside the allowed enum")

    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{path}: string is shorter than minLength")
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            errors.append(f"{path}: string does not match {schema['pattern']!r}")
        if "format" in schema and not valid_format(value, schema["format"]):
            errors.append(f"{path}: invalid {schema['format']} value")
    if isinstance(value, int) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: value is below minimum")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: value is above maximum")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{path}: array is shorter than minItems")
        if schema.get("uniqueItems"):
            encoded = [json.dumps(item, ensure_ascii=False, sort_keys=True) for item in value]
            if len(encoded) != len(set(encoded)):
                errors.append(f"{path}: array items are not unique")
        if isinstance(schema.get("items"), dict):
            for index, item in enumerate(value):
                errors.extend(validate_schema_value(item, schema["items"], root_schema, f"{path}[{index}]"))
    if isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                errors.append(f"{path}: missing required property {key!r}")
        properties = schema.get("properties", {})
        additional = schema.get("additionalProperties", True)
        for key, item in value.items():
            if key in properties:
                errors.extend(validate_schema_value(item, properties[key], root_schema, f"{path}.{key}"))
            elif additional is False:
                errors.append(f"{path}: unexpected property {key!r}")
            elif isinstance(additional, dict):
                errors.extend(validate_schema_value(item, additional, root_schema, f"{path}.{key}"))
    return errors


def duplicates(values: list[str]) -> list[str]:
    return sorted(value for value, count in Counter(values).items() if count > 1)


def walk_strings(value: Any, path: str = "$") -> list[tuple[str, str]]:
    if isinstance(value, str):
        return [(path, value)]
    if isinstance(value, list):
        return [pair for index, item in enumerate(value) for pair in walk_strings(item, f"{path}[{index}]")]
    if isinstance(value, dict):
        return [pair for key, item in value.items() for pair in walk_strings(item, f"{path}.{key}")]
    return []


def expected_summary(universities: list[dict[str, Any]], review_items: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "confirmed_total": sum(item["active_status"] == "confirmed" for item in universities),
        "state_total": sum(item["ownership_type"] == "state" for item in universities),
        "private_total": sum(item["ownership_type"] == "private" for item in universities),
        "cities_total": len({item["city"] for item in universities}),
        "with_admissions_url": sum(item["admissions_url"] is not None for item in universities),
        "monitoring_candidates": sum(
            item["automation_assessment"]["current_monitoring_status"] == "candidate" for item in universities
        ),
        "online_monitoring": sum(
            item["automation_assessment"]["current_monitoring_status"] == "online" for item in universities
        ),
        "needs_review": len(review_items),
    }


def validate_research(data: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    errors = validate_schema_value(data, schema, schema, "$")
    universities = data.get("universities", [])
    review_items = data.get("review_items", [])
    if not isinstance(universities, list) or not isinstance(review_items, list):
        return errors

    for field in ("code", "slug", "official_site_url"):
        repeated = duplicates([item[field] for item in universities if item.get(field) is not None])
        if repeated:
            errors.append(f"Duplicate {field}: {', '.join(repeated)}")

    for item in universities:
        if item.get("active_status") == "confirmed":
            for field in ("full_name", "city", "region", "official_registry_url", "source_checked_at"):
                if not item.get(field):
                    errors.append(f"{item.get('code', '<unknown>')}: confirmed record lacks {field}")
        expected_urls = {
            item["official_site_url"],
            item["official_registry_url"],
            *item["data_sources"].values(),
        }
        if item["admissions_url"]:
            expected_urls.add(item["admissions_url"])
        checked_urls = {
            url
            for check in item["source_checks"]
            for url in (check["url"], check["final_url"])
            if url is not None
        }
        if missing_urls := expected_urls - checked_urls:
            errors.append(f"{item['code']}: URLs lack source checks: {sorted(missing_urls)}")

    for item in review_items:
        checked_urls = {
            url
            for check in item["source_checks"]
            for url in (check["url"], check["final_url"])
            if url is not None
        }
        if missing_urls := set(item["sources"]) - checked_urls:
            errors.append(f"Review item {item['name']!r} lacks source checks: {sorted(missing_urls)}")

    calculated = expected_summary(universities, review_items)
    if data.get("summary") != calculated:
        errors.append(f"Summary mismatch: expected {calculated}, got {data.get('summary')}")

    for path, value in walk_strings(data):
        if value == "":
            errors.append(f"{path}: empty string is not allowed")
        if value.startswith(("http://", "https://")):
            host = (urlparse(value).hostname or "").lower()
            if host in PLACEHOLDER_HOSTS or any(marker in value.lower() for marker in ("placeholder", "todo")):
                errors.append(f"{path}: placeholder URL is not allowed")

    online = [
        item["code"]
        for item in universities
        if item["automation_assessment"]["current_monitoring_status"] == "online"
    ]
    if online != ["bseu"]:
        errors.append(f"Only bseu may be online at this milestone, got {online}")
    return errors


def main() -> int:
    try:
        data = load_json(DATA_PATH)
        schema = load_json(SCHEMA_PATH)
        if not isinstance(data, dict) or not isinstance(schema, dict):
            raise ValidationFailure("The data and schema roots must be JSON objects")
        errors = validate_research(data, schema)
    except ValidationFailure as exc:
        print(f"Research validation failed: {exc}", file=sys.stderr)
        return 1

    if errors:
        print("Research validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    summary = data["summary"]
    print(
        "University research valid: "
        f"{summary['confirmed_total']} confirmed, "
        f"{summary['state_total']} state, "
        f"{summary['private_total']} private, "
        f"{summary['with_admissions_url']} admissions URLs, "
        f"{summary['monitoring_candidates']} candidates, "
        f"{summary['online_monitoring']} online, "
        f"{summary['needs_review']} review items."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
