#!/usr/bin/env python3
"""Check whether an artifact's recorded review date is still fresh.

Works on any of the package's JSON artifacts: it looks for a ``review`` or
``policy_review`` object (whichever the schema in question uses) carrying
a ``reviewed_at`` RFC 3339 timestamp. When that object also carries
``max_age_days``/``fail_age_days`` (as ``fixture-manifest`` does), those
thresholds are used; otherwise this script falls back to its own
documented defaults so every artifact type -- not just fixtures -- can be
freshness-checked.

``--now`` makes the "current time" an explicit, reproducible input instead
of an implicit wall-clock read, so this script's output is deterministic
for a given ``--now``. Omitting it falls back to the real current time,
which is the only way a freshness check is useful outside of tests.

Standard library only. No network access.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NamedTuple

import schema_support

# Fallback thresholds for artifact types whose schema does not declare its
# own max_age_days/fail_age_days (only fixture-manifest does today). A
# yearly re-review cadence with a 6-month warning window is a reasonable,
# documented default for engineering/policy review artifacts.
DEFAULT_MAX_AGE_DAYS = 180
DEFAULT_FAIL_AGE_DAYS = 365

_REVIEW_BLOCK_KEYS = ("review", "policy_review")


class Finding(NamedTuple):
    path: str
    code: str
    message: str


def _find_review_block(instance: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    for key in _REVIEW_BLOCK_KEYS:
        block = instance.get(key)
        if isinstance(block, dict) and "reviewed_at" in block:
            return key, block
    return None


def evaluate(instance: Any, now: datetime, *, strict: bool = False) -> list[Finding]:
    """Return freshness findings for ``instance`` as of ``now``.

    Empty list means the artifact is fresh. A ``stale`` code always fails;
    an ``aging`` (warn) code only fails when ``strict`` is set.
    """
    if not isinstance(instance, dict):
        return [Finding("$", "no_review", "artifact is not a JSON object")]

    located = _find_review_block(instance)
    if located is None:
        return [Finding("$", "no_review", "no 'review' or 'policy_review' object with 'reviewed_at' found")]
    block_key, block = located

    reviewed_at_raw = block.get("reviewed_at")
    reviewed_at = schema_support.parse_rfc3339(reviewed_at_raw) if isinstance(reviewed_at_raw, str) else None
    if reviewed_at is None:
        return [Finding(f"$.{block_key}.reviewed_at", "invalid_review_date", f"not a valid RFC 3339 date-time: {reviewed_at_raw!r}")]

    if reviewed_at.tzinfo is None:
        reviewed_at = reviewed_at.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    age_days = (now - reviewed_at).days
    if age_days < 0:
        return [
            Finding(
                f"$.{block_key}.reviewed_at",
                "invalid_review_date",
                f"reviewed_at {reviewed_at_raw!r} is in the future relative to --now",
            )
        ]

    max_age_days = block.get("max_age_days")
    if not isinstance(max_age_days, int):
        max_age_days = DEFAULT_MAX_AGE_DAYS
    fail_age_days = block.get("fail_age_days")
    if not isinstance(fail_age_days, int):
        fail_age_days = DEFAULT_FAIL_AGE_DAYS

    if age_days > fail_age_days:
        return [
            Finding(
                f"$.{block_key}.reviewed_at",
                "stale",
                f"reviewed {age_days} day(s) ago, exceeding fail_age_days={fail_age_days}",
            )
        ]
    if age_days > max_age_days:
        return [
            Finding(
                f"$.{block_key}.reviewed_at",
                "aging",
                f"reviewed {age_days} day(s) ago, exceeding max_age_days={max_age_days} (not yet fail_age_days={fail_age_days})",
            )
        ]

    return []


def _is_failing(findings: list[Finding], *, strict: bool) -> bool:
    for finding in findings:
        if finding.code in ("stale", "no_review", "invalid_review_date"):
            return True
        if finding.code == "aging" and strict:
            return True
    return False


# --- CLI -------------------------------------------------------------------


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="check_freshness.py",
        description="Check an artifact's review date against warn/fail age thresholds.",
    )
    parser.add_argument("path", type=Path, help="JSON artifact with a review/policy_review.reviewed_at field")
    parser.add_argument("--now", metavar="RFC3339", default=None, help="treat this RFC 3339 timestamp as the current time (default: real current time)")
    parser.add_argument("--strict", action="store_true", help="treat an 'aging' warning as a failure too")
    parser.add_argument("--json", action="store_true", help="emit findings as JSON")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    if args.now is None:
        now = datetime.now(timezone.utc)
    else:
        now = schema_support.parse_rfc3339(args.now)
        if now is None:
            print(f"USAGE_ERROR: --now is not a valid RFC 3339 date-time: {args.now!r}", file=sys.stderr)
            return 2

    try:
        instance = schema_support.load_json(args.path)
    except schema_support.JsonLoadError as error:
        print(f"JSON_LOAD_ERROR: {error}", file=sys.stderr)
        return 2

    findings = evaluate(instance, now, strict=args.strict)
    failing = _is_failing(findings, strict=args.strict)

    if args.json:
        payload = {
            "ok": not failing,
            "path": str(args.path),
            "now": now.isoformat(),
            "issues": [f._asdict() for f in findings],
        }
        print(json.dumps(payload, sort_keys=True))
    else:
        for finding in findings:
            stream = sys.stderr if finding.code != "aging" or args.strict else sys.stdout
            print(f"{finding.code} {finding.path}: {finding.message}", file=stream)
        if failing:
            print(f"FRESHNESS_FAIL: {args.path}", file=sys.stderr)
        else:
            print(f"FRESHNESS_OK: {args.path}")

    return 1 if failing else 0


if __name__ == "__main__":
    raise SystemExit(main())
