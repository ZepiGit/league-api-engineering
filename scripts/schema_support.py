#!/usr/bin/env python3
"""Dependency-free JSON helpers and a deliberate JSON-Schema validation subset."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit


@dataclass(frozen=True)
class ValidationIssue:
    """One deterministic validation failure."""

    path: str
    keyword: str
    message: str

    def render(self) -> str:
        return f"{self.keyword} {self.path}: {self.message}"


class JsonLoadError(ValueError):
    """Raised when a JSON artifact cannot be loaded."""


def load_json(path: Path) -> Any:
    """Load a UTF-8 JSON artifact with a path-bearing error."""
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as error:
        raise JsonLoadError(f"missing JSON artifact: {path}") from error
    except UnicodeDecodeError as error:
        raise JsonLoadError(f"artifact is not UTF-8: {path}: {error}") from error
    except json.JSONDecodeError as error:
        raise JsonLoadError(
            f"invalid JSON in {path}:{error.lineno}:{error.colno}: {error.msg}"
        ) from error


def canonical_json_bytes(value: Any) -> bytes:
    """Return stable UTF-8 JSON bytes suitable for a content fingerprint."""
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_json_sha256(value: Any) -> str:
    """Return the canonical JSON SHA-256 fingerprint."""
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def parse_rfc3339(value: str) -> datetime | None:
    """Parse the RFC 3339 date-time subset required by package schemas."""
    if not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})",
        value,
    ):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def is_uri(value: str) -> bool:
    """Check that a string is an absolute URI without whitespace."""
    if not value or any(character.isspace() for character in value):
        return False
    parsed = urlsplit(value)
    if not parsed.scheme:
        return False
    if parsed.scheme in {"http", "https"}:
        return bool(parsed.netloc)
    return True


def find_package_root(path: Path) -> Path | None:
    """Find the nearest ancestor that owns the public schemas directory."""
    candidate = path.resolve()
    if candidate.is_file():
        candidate = candidate.parent
    for ancestor in (candidate, *candidate.parents):
        if (ancestor / "schemas").is_dir():
            return ancestor
    return None


def _json_equal(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(
            _json_equal(left[key], right[key]) for key in left
        )
    if isinstance(left, list):
        return len(left) == len(right) and all(
            _json_equal(a, b) for a, b in zip(left, right)
        )
    return left == right


def _type_matches(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return False


def _child_path(path: str, key: str) -> str:
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
        return f"{path}.{key}"
    return f"{path}[{json.dumps(key, ensure_ascii=False)}]"


def _append(
    issues: list[ValidationIssue], path: str, keyword: str, message: str
) -> None:
    issues.append(ValidationIssue(path=path, keyword=keyword, message=message))


def _validate(schema: Any, instance: Any, path: str, issues: list[ValidationIssue]) -> None:
    if schema is True:
        return
    if schema is False:
        _append(issues, path, "falseSchema", "value is disallowed")
        return
    if not isinstance(schema, dict):
        _append(issues, path, "schema", "schema must be an object or boolean")
        return

    if "allOf" in schema:
        branches = schema["allOf"]
        if not isinstance(branches, list):
            _append(issues, path, "schema", "allOf must be an array")
        else:
            for branch in branches:
                _validate(branch, instance, path, issues)

    if "anyOf" in schema:
        branches = schema["anyOf"]
        if not isinstance(branches, list) or not branches:
            _append(issues, path, "schema", "anyOf must be a non-empty array")
        else:
            matches = 0
            for branch in branches:
                branch_issues: list[ValidationIssue] = []
                _validate(branch, instance, path, branch_issues)
                if not branch_issues:
                    matches += 1
            if not matches:
                _append(issues, path, "anyOf", "value does not satisfy any branch")

    if "oneOf" in schema:
        branches = schema["oneOf"]
        if not isinstance(branches, list) or not branches:
            _append(issues, path, "schema", "oneOf must be a non-empty array")
        else:
            matches = 0
            for branch in branches:
                branch_issues = []
                _validate(branch, instance, path, branch_issues)
                if not branch_issues:
                    matches += 1
            if matches != 1:
                _append(
                    issues,
                    path,
                    "oneOf",
                    f"value satisfies {matches} branches; exactly one is required",
                )

    if "const" in schema and not _json_equal(instance, schema["const"]):
        _append(issues, path, "const", f"must equal {json.dumps(schema['const'])}")

    if "enum" in schema:
        choices = schema["enum"]
        if not isinstance(choices, list):
            _append(issues, path, "schema", "enum must be an array")
        elif not any(_json_equal(instance, choice) for choice in choices):
            _append(issues, path, "enum", "value is not an allowed choice")

    expected_type = schema.get("type")
    if expected_type is not None:
        expected_types = expected_type if isinstance(expected_type, list) else [expected_type]
        if not all(isinstance(name, str) for name in expected_types):
            _append(issues, path, "schema", "type must be a string or string array")
        elif not any(_type_matches(instance, name) for name in expected_types):
            expected = " or ".join(expected_types)
            _append(issues, path, "type", f"expected {expected}")
            return

    if isinstance(instance, dict):
        _validate_object(schema, instance, path, issues)
    if isinstance(instance, list):
        _validate_array(schema, instance, path, issues)
    if isinstance(instance, str):
        _validate_string(schema, instance, path, issues)
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        _validate_number(schema, instance, path, issues)


def _validate_object(
    schema: dict[str, Any], instance: dict[str, Any], path: str, issues: list[ValidationIssue]
) -> None:
    required = schema.get("required", [])
    if not isinstance(required, list) or not all(isinstance(key, str) for key in required):
        _append(issues, path, "schema", "required must be an array of strings")
    else:
        for key in required:
            if key not in instance:
                _append(issues, path, "required", f"missing required property {key!r}")

    min_properties = schema.get("minProperties")
    max_properties = schema.get("maxProperties")
    if isinstance(min_properties, int) and len(instance) < min_properties:
        _append(issues, path, "minProperties", f"expected at least {min_properties} properties")
    if isinstance(max_properties, int) and len(instance) > max_properties:
        _append(issues, path, "maxProperties", f"expected at most {max_properties} properties")

    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        _append(issues, path, "schema", "properties must be an object")
        properties = {}
    for key in sorted(properties):
        if key in instance:
            _validate(properties[key], instance[key], _child_path(path, key), issues)

    additional = schema.get("additionalProperties", True)
    for key in sorted(instance):
        if key in properties:
            continue
        if additional is False:
            _append(issues, _child_path(path, key), "additionalProperties", "property is not allowed")
        elif isinstance(additional, (dict, bool)):
            _validate(additional, instance[key], _child_path(path, key), issues)
        else:
            _append(issues, path, "schema", "additionalProperties must be boolean or schema")
            break


def _validate_array(
    schema: dict[str, Any], instance: list[Any], path: str, issues: list[ValidationIssue]
) -> None:
    minimum = schema.get("minItems")
    maximum = schema.get("maxItems")
    if isinstance(minimum, int) and len(instance) < minimum:
        _append(issues, path, "minItems", f"expected at least {minimum} items")
    if isinstance(maximum, int) and len(instance) > maximum:
        _append(issues, path, "maxItems", f"expected at most {maximum} items")
    if schema.get("uniqueItems") is True:
        for index, value in enumerate(instance):
            if any(_json_equal(value, prior) for prior in instance[:index]):
                _append(issues, f"{path}[{index}]", "uniqueItems", "array item is duplicated")
    items = schema.get("items")
    if items is not None:
        for index, value in enumerate(instance):
            _validate(items, value, f"{path}[{index}]", issues)


def _validate_string(
    schema: dict[str, Any], instance: str, path: str, issues: list[ValidationIssue]
) -> None:
    minimum = schema.get("minLength")
    maximum = schema.get("maxLength")
    if isinstance(minimum, int) and len(instance) < minimum:
        _append(issues, path, "minLength", f"expected length at least {minimum}")
    if isinstance(maximum, int) and len(instance) > maximum:
        _append(issues, path, "maxLength", f"expected length at most {maximum}")
    pattern = schema.get("pattern")
    if pattern is not None:
        if not isinstance(pattern, str):
            _append(issues, path, "schema", "pattern must be a string")
        else:
            try:
                if re.search(pattern, instance) is None:
                    _append(issues, path, "pattern", f"does not match {pattern!r}")
            except re.error as error:
                _append(issues, path, "schema", f"invalid pattern: {error}")
    value_format = schema.get("format")
    if value_format == "date-time" and parse_rfc3339(instance) is None:
        _append(issues, path, "format", "must be an RFC 3339 date-time")
    elif value_format == "uri" and not is_uri(instance):
        _append(issues, path, "format", "must be an absolute URI")


def _validate_number(
    schema: dict[str, Any], instance: int | float, path: str, issues: list[ValidationIssue]
) -> None:
    minimum = schema.get("minimum")
    maximum = schema.get("maximum")
    if isinstance(minimum, (int, float)) and instance < minimum:
        _append(issues, path, "minimum", f"must be at least {minimum}")
    if isinstance(maximum, (int, float)) and instance > maximum:
        _append(issues, path, "maximum", f"must be at most {maximum}")


def validate_instance(instance: Any, schema: Any) -> list[ValidationIssue]:
    """Validate an instance against the documented subset in stable order."""
    issues: list[ValidationIssue] = []
    _validate(schema, instance, "$", issues)
    return issues


def print_issues(issues: Iterable[ValidationIssue], stream: Any = sys.stderr) -> None:
    """Print validation issues one per line."""
    for issue in issues:
        print(issue.render(), file=stream)


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate one JSON instance against the package's dependency-free schema subset."
    )
    parser.add_argument("schema", type=Path, help="schema JSON file")
    parser.add_argument("instance", type=Path, help="instance JSON file")
    parser.add_argument("--json", action="store_true", help="emit issues as JSON")
    args = parser.parse_args(argv)
    try:
        schema = load_json(args.schema)
        instance = load_json(args.instance)
    except JsonLoadError as error:
        print(f"JSON_LOAD_ERROR: {error}", file=sys.stderr)
        return 2
    issues = validate_instance(instance, schema)
    if args.json:
        print(json.dumps([issue.__dict__ for issue in issues], sort_keys=True))
    elif issues:
        print_issues(issues)
    if issues:
        print(f"SCHEMA_INVALID: {args.instance}", file=sys.stderr)
        return 1
    print(f"SCHEMA_VALID: {args.instance}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
