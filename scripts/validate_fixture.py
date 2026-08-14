#!/usr/bin/env python3
"""Validate a ``fixture-manifest`` artifact and the payload files it lists.

Schema conformance is delegated to ``schema_support``. On top of that this
script:

- Rejects any ``files[].path`` that would resolve outside the manifest's
  own directory once joined and normalized (path traversal via ``..``,
  a POSIX-style absolute path, or a Windows drive-letter path all collapse
  to the same containment check).
- Scans every payload file that exists on disk for the same secret and
  PII-shaped patterns ``security_scan.py`` looks for, so a fixture cannot
  ship a real Riot key, auth token, cookie, or user path merely because it
  sits in a payload file instead of the manifest itself.

Standard library only. No network access.
"""

from __future__ import annotations
import hashlib

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, NamedTuple

import schema_support
import security_scan

SCHEMA_ID = "fixture-manifest"
SCHEMA_FILE = "fixture-manifest.schema.json"

# Riot PUUIDs and similar opaque player identifiers are long base64url-ish
# tokens assigned to an identifying-looking key. Kept narrow (assignment
# context required) to avoid flagging unrelated long hex/base64 values such
# as the sha256 hashes this same schema legitimately carries.
_PII_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(puuid|summoner[_-]?name|account[_-]?id|player[_-]?id|email)\b\s*[:=]\s*['\"][^'\"\s]{6,}['\"]"
)
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[A-Za-z]{2,}\b")


class Finding(NamedTuple):
    path: str
    code: str
    message: str


def _check_path_traversal(manifest_dir: Path, entry_path: str) -> Finding | None:
    base = manifest_dir.resolve()
    try:
        resolved = (manifest_dir / entry_path).resolve()
    except (OSError, ValueError) as error:
        return Finding(f"$.files[path={entry_path!r}]", "path_traversal", f"cannot resolve path: {error}")
    if resolved != base and base not in resolved.parents:
        return Finding(
            f"$.files[path={entry_path!r}]",
            "path_traversal",
            f"resolves outside the fixture-manifest directory: {resolved}",
        )
    return None


def _scan_payload(manifest_dir: Path, entry_path: str, expected_sha256: Any) -> list[Finding]:
    findings: list[Finding] = []
    resolved = (manifest_dir / entry_path).resolve()
    if not resolved.is_file():
        return [
            Finding(
                f"$.files[path={entry_path!r}]",
                "missing_payload",
                f"referenced fixture payload does not exist: {entry_path}",
            )
        ]

    data = resolved.read_bytes()
    actual_sha256 = hashlib.sha256(data).hexdigest()
    if isinstance(expected_sha256, str) and actual_sha256 != expected_sha256:
        findings.append(
            Finding(
                f"$.files[path={entry_path!r}].sha256",
                "hash_mismatch",
                f"declared {expected_sha256}, actual {actual_sha256}",
            )
        )
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return findings

    label = f"files/{entry_path}"
    for scan_finding in security_scan.scan_text(text, label):
        findings.append(Finding(f"$.files[path={entry_path!r}]", scan_finding.code, f"{label}:{scan_finding.line}: {scan_finding.message}"))

    for line_no, line in enumerate(text.splitlines(), start=1):
        match = _PII_ASSIGNMENT_RE.search(line) or _EMAIL_RE.search(line)
        if match:
            findings.append(
                Finding(
                    f"$.files[path={entry_path!r}]",
                    "pii",
                    f"{label}:{line_no}: possible personal data: {match.group(0)!r}",
                )
            )

    return findings


def evaluate(instance: Any, schema: Any, manifest_path: Path) -> list[Finding]:
    """Schema-validate ``instance`` and scan the fixture files it declares."""
    findings: list[Finding] = []

    for issue in schema_support.validate_instance(instance, schema):
        findings.append(Finding(issue.path, "schema", issue.render()))

    if not isinstance(instance, dict):
        return findings

    files = instance.get("files")
    if not isinstance(files, list):
        return findings

    manifest_dir = manifest_path.parent
    for entry in files:
        if not isinstance(entry, dict):
            continue
        entry_path = entry.get("path")
        if not isinstance(entry_path, str):
            continue

        traversal = _check_path_traversal(manifest_dir, entry_path)
        if traversal is not None:
            findings.append(traversal)
            continue  # do not read a file we just proved escapes the fixture root


        findings.extend(_scan_payload(manifest_dir, entry_path, entry.get("sha256")))
    return findings


# --- CLI -------------------------------------------------------------------


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="validate_fixture.py",
        description="Validate a fixture-manifest artifact: schema plus secret/PII and path-traversal scanning of its payloads.",
    )
    parser.add_argument("path", type=Path, help="fixture-manifest JSON artifact")
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

    findings = evaluate(instance, schema, args.path)

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
            print(f"FIXTURE_MANIFEST_INVALID: {args.path}", file=sys.stderr)
        else:
            print(f"FIXTURE_MANIFEST_VALID: {args.path}")

    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
