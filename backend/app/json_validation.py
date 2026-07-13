from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


class JsonDocumentError(ValueError):
    pass


def load_json_document(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise JsonDocumentError(f"Cannot load JSON document {path}: {exc}") from exc


def _resolve_ref(root_schema: dict[str, Any], ref: str) -> dict[str, Any]:
    if not ref.startswith("#/"):
        raise JsonDocumentError(f"Only local schema references are supported: {ref}")
    value: Any = root_schema
    try:
        for part in ref[2:].split("/"):
            value = value[part.replace("~1", "/").replace("~0", "~")]
    except (KeyError, TypeError) as exc:
        raise JsonDocumentError(f"Invalid schema reference: {ref}") from exc
    if not isinstance(value, dict):
        raise JsonDocumentError(f"Schema reference does not resolve to an object: {ref}")
    return value


def _is_type(value: Any, expected: str) -> bool:
    return {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": isinstance(value, int | float) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "null": value is None,
    }.get(expected, False)


def _valid_format(value: str, format_name: str) -> bool:
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
    path: str = "$",
) -> list[str]:
    if "$ref" in schema:
        return validate_schema_value(value, _resolve_ref(root_schema, schema["$ref"]), root_schema, path)
    if "oneOf" in schema:
        matches = [
            branch
            for branch in schema["oneOf"]
            if not validate_schema_value(value, branch, root_schema, path)
        ]
        return [] if len(matches) == 1 else [f"{path}: expected exactly one oneOf branch, got {len(matches)}"]

    errors: list[str] = []
    expected_type = schema.get("type")
    if expected_type and not _is_type(value, expected_type):
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
        if "format" in schema and not _valid_format(value, schema["format"]):
            errors.append(f"{path}: invalid {schema['format']} value")
    if isinstance(value, int | float) and not isinstance(value, bool):
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
        for key in schema.get("required", []):
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


def validate_json_document(data: Any, schema: Any) -> None:
    if not isinstance(schema, dict):
        raise JsonDocumentError("JSON Schema root must be an object")
    errors = validate_schema_value(data, schema, schema)
    if errors:
        preview = "; ".join(errors[:10])
        remainder = len(errors) - 10
        suffix = f"; and {remainder} more" if remainder > 0 else ""
        raise JsonDocumentError(f"JSON Schema validation failed: {preview}{suffix}")


def load_and_validate_json(data_path: Path, schema_path: Path) -> Any:
    data = load_json_document(data_path)
    schema = load_json_document(schema_path)
    validate_json_document(data, schema)
    return data
