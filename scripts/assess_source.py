#!/usr/bin/env python3
"""Validate a ``source-assessment`` artifact and its recommendation.

Schema conformance is delegated to ``schema_support``. On top of that this
script:

1. Rejects any artifact where a hard gate (``requires_embedded_secret``,
   ``unsafe_technique``, ``unsupported_data``, ``redistribution_unverified``)
   is set, regardless of the declared or computed recommendation. A hard
   gate is an unconditional reject.
2. Computes a deterministic recommendation from the twelve 0-5 dimension
   scores (equal-weight mean) and flags a mismatch against the artifact's
   own declared ``recommendation`` when the two disagree.

Standard library only. No network access.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, NamedTuple

import schema_support

SCHEMA_ID = "source-assessment"
SCHEMA_FILE = "source-assessment.schema.json"

# Required dimension keys, in the order documented by the schema. Equal
# weight keeps the score reproducible without inventing an undocumented
# weighting scheme.
DIMENSIONS: tuple[str, ...] = (
    "authority",
    "authentication_feasibility",
    "routing",
    "local_compatibility",
    "latency",
    "stability",
    "patch_coverage",
    "terms",
    "rate_limits",
    "privacy",
    "attribution",
    "failure_behavior",
)

HARD_GATE_KEYS: tuple[str, ...] = (
    "requires_embedded_secret",
    "unsafe_technique",
    "unsupported_data",
    "redistribution_unverified",
)

# A dimension mean at or above APPROVED_THRESHOLD recommends "approved";
# at or above CONDITIONAL_THRESHOLD (but below APPROVED_THRESHOLD)
# recommends "conditional"; below that, "rejected". Both thresholds are
# this script's own documented, deterministic policy -- they are not
# derived from the schema, which intentionally leaves scoring open.
APPROVED_THRESHOLD = 4.0
CONDITIONAL_THRESHOLD = 2.5


class Finding(NamedTuple):
    path: str
    code: str
    message: str


def compute_recommendation(instance: dict[str, Any]) -> tuple[str, float | None]:
    """Return ``(recommendation, mean_score)`` computed from hard gates and dimensions."""
    hard_gates = instance.get("hard_gates", {})
    if isinstance(hard_gates, dict) and any(bool(hard_gates.get(key)) for key in HARD_GATE_KEYS):
        return "rejected", None

    dimensions = instance.get("dimensions", {})
    if not isinstance(dimensions, dict):
        return "rejected", None
    values = [dimensions[key] for key in DIMENSIONS if isinstance(dimensions.get(key), (int, float))]
    if len(values) != len(DIMENSIONS):
        return "rejected", None

    mean_score = sum(values) / len(values)
    if mean_score >= APPROVED_THRESHOLD:
        return "approved", mean_score
    if mean_score >= CONDITIONAL_THRESHOLD:
        return "conditional", mean_score
    return "rejected", mean_score


def evaluate(instance: Any, schema: Any) -> list[Finding]:
    """Schema-validate ``instance`` and apply source-assessment semantics."""
    findings: list[Finding] = []

    for issue in schema_support.validate_instance(instance, schema):
        findings.append(Finding(issue.path, "schema", issue.render()))

    if not isinstance(instance, dict):
        return findings

    hard_gates = instance.get("hard_gates")
    if isinstance(hard_gates, dict):
        tripped = [key for key in HARD_GATE_KEYS if bool(hard_gates.get(key))]
        for key in tripped:
            findings.append(
                Finding(
                    f"$.hard_gates.{key}",
                    "hard_gate",
                    f"hard gate {key!r} is set; source is rejected regardless of score or declared recommendation",
                )
            )

    computed, mean_score = compute_recommendation(instance)
    declared = instance.get("recommendation")
    if isinstance(declared, str) and declared != computed:
        detail = f"computed {mean_score:.3f} mean" if mean_score is not None else "hard gate forces rejection"
        findings.append(
            Finding(
                "$.recommendation",
                "recommendation_mismatch",
                f"declared recommendation {declared!r} does not match computed {computed!r} ({detail})",
            )
        )

    return findings


# --- CLI -------------------------------------------------------------------


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="assess_source.py",
        description="Validate a source-assessment artifact: schema, hard gates, and recommendation consistency.",
    )
    parser.add_argument("path", type=Path, help="source-assessment JSON artifact")
    parser.add_argument("--root", type=Path, default=None, help="package root (default: nearest ancestor with schemas/)")
    parser.add_argument("--json", action="store_true", help="emit findings as JSON")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    root = args.root if args.root is not None else schema_support.find_package_root(args.path)
    if root is None:
        print(f"PACKAGE_ROOT_NOT_FOUND: no schemas/ directory above {args.path}", file=sys.stderr)
        return 2

    try:
        schema = schema_support.load_json(root / "schemas" / SCHEMA_FILE)
        instance = schema_support.load_json(args.path)
    except schema_support.JsonLoadError as error:
        print(f"JSON_LOAD_ERROR: {error}", file=sys.stderr)
        return 2

    if isinstance(instance, dict) and instance.get("schema_id") not in (None, SCHEMA_ID):
        print(f"SCHEMA_ID_MISMATCH: {args.path} declares {instance.get('schema_id')!r}, expected {SCHEMA_ID!r}", file=sys.stderr)
        return 2

    findings = evaluate(instance, schema)

    if args.json:
        payload = {
            "ok": not findings,
            "path": str(args.path),
            "issues": [f._asdict() for f in findings],
        }
        print(json.dumps(payload, sort_keys=True))
    else:
        for finding in findings:
            print(f"{finding.code} {finding.path}: {finding.message}", file=sys.stderr)
        if findings:
            print(f"SOURCE_ASSESSMENT_INVALID: {args.path}", file=sys.stderr)
        else:
            print(f"SOURCE_ASSESSMENT_VALID: {args.path}")

    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
