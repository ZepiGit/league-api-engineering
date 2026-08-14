#!/usr/bin/env python3
"""Compare two JSON documents by their canonical-JSON SHA-256 fingerprint.

Two independently captured JSON artifacts (a baseline snapshot and a
current one, or a shipped fixture and a freshly captured payload) either
serialize to the same canonical bytes or they do not; this tool makes that
comparison deterministic and offline, using
``schema_support.canonical_json_sha256`` so drift detection here always
agrees with any other tool in this package that fingerprints the same way.

Two modes:

- ``check_drift.py <baseline> <current>`` -- compare two JSON files.
- ``check_drift.py <path> --expect <sha256>`` -- compare one JSON file's
  fingerprint against a previously recorded hex digest (useful for a
  contract that pins an expected fingerprint without shipping the whole
  baseline document alongside it).

Standard library only. No network access.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import schema_support

_HEX64_RE = re.compile(r"^[a-f0-9]{64}$")


def fingerprint(instance: Any) -> str:
    """Return the canonical-JSON SHA-256 fingerprint of ``instance``."""
    return schema_support.canonical_json_sha256(instance)


def _diff_top_level_keys(a: Any, b: Any) -> list[str]:
    """Best-effort human hint about what changed, without claiming completeness."""
    if not isinstance(a, dict) or not isinstance(b, dict):
        return ["document is not a JSON object at the top level; only the fingerprint differs"]
    notes: list[str] = []
    for key in sorted(set(a) | set(b)):
        if key not in a:
            notes.append(f"+{key} (only in second document)")
        elif key not in b:
            notes.append(f"-{key} (only in first document)")
        elif a[key] != b[key]:
            notes.append(f"~{key} (value differs)")
    return notes


def compare(a: Any, b: Any) -> tuple[bool, str, str, list[str]]:
    """Return ``(drift_free, fingerprint_a, fingerprint_b, diff_notes)``."""
    fp_a = fingerprint(a)
    fp_b = fingerprint(b)
    if fp_a == fp_b:
        return True, fp_a, fp_b, []
    return False, fp_a, fp_b, _diff_top_level_keys(a, b)


# --- CLI -------------------------------------------------------------------


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="check_drift.py",
        description="Compare JSON documents by canonical-JSON SHA-256 fingerprint, offline.",
    )
    parser.add_argument("a", type=Path, help="first JSON document")
    parser.add_argument("b", type=Path, nargs="?", default=None, help="second JSON document (omit when using --expect)")
    parser.add_argument("--expect", metavar="SHA256", default=None, help="compare 'a' against a recorded 64-hex-char fingerprint instead of a second file")
    parser.add_argument("--json", action="store_true", help="emit the result as JSON")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    if args.expect is None and args.b is None:
        print("USAGE_ERROR: provide either a second document or --expect SHA256", file=sys.stderr)
        return 2
    if args.expect is not None and args.b is not None:
        print("USAGE_ERROR: provide a second document or --expect SHA256, not both", file=sys.stderr)
        return 2
    if args.expect is not None and not _HEX64_RE.match(args.expect):
        print(f"USAGE_ERROR: --expect must be a 64-character lowercase hex sha256, got {args.expect!r}", file=sys.stderr)
        return 2

    try:
        doc_a = schema_support.load_json(args.a)
    except schema_support.JsonLoadError as error:
        print(f"JSON_LOAD_ERROR: {error}", file=sys.stderr)
        return 2

    if args.expect is not None:
        fp_a = fingerprint(doc_a)
        drift_free = fp_a == args.expect
        fp_b = args.expect
        diff_notes: list[str] = [] if drift_free else ["fingerprint does not match --expect"]
        label_b = "--expect"
    else:
        try:
            doc_b = schema_support.load_json(args.b)
        except schema_support.JsonLoadError as error:
            print(f"JSON_LOAD_ERROR: {error}", file=sys.stderr)
            return 2
        drift_free, fp_a, fp_b, diff_notes = compare(doc_a, doc_b)
        label_b = str(args.b)

    if args.json:
        payload = {
            "ok": drift_free,
            "a": str(args.a),
            "b": label_b,
            "fingerprint_a": fp_a,
            "fingerprint_b": fp_b,
            "diff": diff_notes,
        }
        print(json.dumps(payload, sort_keys=True))
    else:
        if drift_free:
            print(f"DRIFT_NONE: {args.a} == {label_b} ({fp_a})")
        else:
            print(f"drift {args.a}: fingerprint {fp_a}", file=sys.stderr)
            print(f"drift {label_b}: fingerprint {fp_b}", file=sys.stderr)
            for note in diff_notes:
                print(f"drift {note}", file=sys.stderr)
            print(f"DRIFT_DETECTED: {args.a} != {label_b}", file=sys.stderr)

    return 0 if drift_free else 1


if __name__ == "__main__":
    raise SystemExit(main())
