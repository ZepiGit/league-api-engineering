#!/usr/bin/env python3
"""Top-level validator for the League API Engineering public package.

Run as ``python scripts/validate.py .`` from the package root before
packaging (see ``AGENTS.md``). Orchestrates, in order:

1. Package structure -- the top-level files, schemas, and scripts a public
   release must ship.
2. Schema conformance of every ``templates/*.json`` and
   ``examples/valid/*.json`` artifact against its declared schema.
3. Each focused validator's *own* semantic checks (not just schema) run
   against the matching ``examples/valid/*.json`` artifact, proving the
   validators accept the package's own good examples.
4. The ``check_drift.py`` tool's self-consistency (identical documents
   fingerprint equal; different documents do not).
5. Every case in ``examples/invalid/manifest.json`` is routed to the
   validator implied by its ``kind`` and must be rejected carrying its
   declared ``expected_code`` -- proving the negative examples actually
   fail for the *documented* reason, not merely fail somehow.
6. The eval suite structural validator (``scripts/run_evals.py``), when
   present -- it ships as part of this same package but is optional input
   to this orchestrator per this script's own contract.
7. A package-wide security scan (``security_scan.py`` semantics), excluding
   ``evals/`` (adversarial eval prompts, validated by run_evals.py instead)
   and ``examples/invalid/`` (deliberately-broken fixtures already proven
   to fail for the right reason in step 5).

Standard library only. No network access.
"""

from __future__ import annotations

import argparse
import json
import sys
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NamedTuple

import assess_source
import check_drift
import check_freshness
import schema_support
import security_scan
import validate_contract
import validate_fixture

REQUIRED_TOP_FILES: tuple[str, ...] = (
    "SKILL.md",
    "AGENTS.md",
    "README.md",
    "LICENSE",
    ".claude-plugin/plugin.json",
    ".claude-plugin/marketplace.json",
    "exports/README.md",
)

REQUIRED_SCHEMAS: tuple[str, ...] = (
    "source-assessment.schema.json",
    "adapter-contract.schema.json",
    "audit-report.schema.json",
    "fixture-manifest.schema.json",
)

REQUIRED_SCRIPTS: tuple[str, ...] = (
    "schema_support.py",
    "validate.py",
    "security_scan.py",
    "assess_source.py",
    "validate_contract.py",
    "validate_fixture.py",
    "check_drift.py",
    "check_freshness.py",
)

_SCHEMA_ID_TO_FILE: dict[str, str] = {
    "source-assessment": "source-assessment.schema.json",
    "adapter-contract": "adapter-contract.schema.json",
    "audit-report": "audit-report.schema.json",
    "fixture-manifest": "fixture-manifest.schema.json",
}

# Subtrees excluded from the package-wide security scan, each with its own
# dedicated validation elsewhere in this orchestrator (see module docstring
# points 5 and 6). This mirrors security_scan.py's own default exclusion of
# evals/ and additionally excludes the intentionally-broken invalid-example
# fixtures, which would otherwise "fail" a global scan for content that
# exists precisely to fail a *targeted* one.
_SECURITY_SCAN_PATH_EXCLUDES: tuple[str, ...] = ("examples/invalid/",)


class Finding(NamedTuple):
    stage: str
    code: str
    message: str


def _load_schema_by_id(root: Path, schema_id: str) -> Any:
    return schema_support.load_json(root / "schemas" / _SCHEMA_ID_TO_FILE[schema_id])


def _check_structure(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for relative in REQUIRED_TOP_FILES:
        if not (root / relative).is_file():
            findings.append(Finding("structure", "missing_file", f"missing required file: {relative}"))
    for name in REQUIRED_SCHEMAS:
        if not (root / "schemas" / name).is_file():
            findings.append(Finding("structure", "missing_schema", f"missing schema: schemas/{name}"))
    for name in REQUIRED_SCRIPTS:
        if not (root / "scripts" / name).is_file():
            findings.append(Finding("structure", "missing_script", f"missing script: scripts/{name}"))
    return findings


def _check_schema_conformance(root: Path, relative_dir: str) -> list[Finding]:
    """Schema-validate every direct *.json child of ``root/relative_dir``."""
    findings: list[Finding] = []
    directory = root / relative_dir
    if not directory.is_dir():
        findings.append(Finding(relative_dir, "missing_dir", f"missing directory: {relative_dir}"))
        return findings

    for path in sorted(directory.glob("*.json")):
        try:
            instance = schema_support.load_json(path)
        except schema_support.JsonLoadError as error:
            findings.append(Finding(relative_dir, "load_error", f"{path.name}: {error}"))
            continue
        schema_id = instance.get("schema_id") if isinstance(instance, dict) else None
        if schema_id not in _SCHEMA_ID_TO_FILE:
            findings.append(Finding(relative_dir, "unknown_schema_id", f"{path.name}: unrecognized schema_id {schema_id!r}"))
            continue
        schema = _load_schema_by_id(root, schema_id)
        for issue in schema_support.validate_instance(instance, schema):
            findings.append(Finding(relative_dir, "schema", f"{path.name} {issue.render()}"))
    return findings


def _check_valid_examples_semantics(root: Path, now: datetime) -> list[Finding]:
    """Run each focused validator's full semantics against examples/valid/*.json."""
    findings: list[Finding] = []
    valid_dir = root / "examples" / "valid"

    def _load(name: str) -> Any | None:
        try:
            return schema_support.load_json(valid_dir / name)
        except schema_support.JsonLoadError as error:
            findings.append(Finding("examples/valid", "load_error", f"{name}: {error}"))
            return None

    source_instance = _load("source-assessment.json")
    if source_instance is not None:
        schema = _load_schema_by_id(root, "source-assessment")
        for issue in assess_source.evaluate(source_instance, schema):
            findings.append(Finding("examples/valid", issue.code, f"source-assessment.json: {issue.message}"))

    contract_instance = _load("adapter-contract.json")
    if contract_instance is not None:
        schema = _load_schema_by_id(root, "adapter-contract")
        for issue in validate_contract.evaluate(contract_instance, schema):
            findings.append(Finding("examples/valid", issue.code, f"adapter-contract.json: {issue.message}"))

    fixture_instance = _load("fixture-manifest.json")
    if fixture_instance is not None:
        schema = _load_schema_by_id(root, "fixture-manifest")
        fixture_path = valid_dir / "fixture-manifest.json"
        for issue in validate_fixture.evaluate(fixture_instance, schema, fixture_path):
            findings.append(Finding("examples/valid", issue.code, f"fixture-manifest.json: {issue.message}"))
        for issue in check_freshness.evaluate(fixture_instance, now):
            findings.append(Finding("examples/valid", issue.code, f"fixture-manifest.json: {issue.message}"))

    return findings


def _check_drift_tool(root: Path) -> list[Finding]:
    """Smoke-test check_drift.py's own logic: self-fingerprint, then a real diff."""
    findings: list[Finding] = []
    try:
        contract_schema = schema_support.load_json(root / "schemas" / "adapter-contract.schema.json")
        report_schema = schema_support.load_json(root / "schemas" / "audit-report.schema.json")
    except schema_support.JsonLoadError as error:
        findings.append(Finding("drift", "load_error", str(error)))
        return findings

    same_ok, _, _, _ = check_drift.compare(contract_schema, contract_schema)
    if not same_ok:
        findings.append(Finding("drift", "tool_self_check_failed", "identical documents did not fingerprint equal"))

    diff_ok, _, _, _ = check_drift.compare(contract_schema, report_schema)
    if diff_ok:
        findings.append(Finding("drift", "tool_self_check_failed", "different documents fingerprinted equal"))

    return findings


def _check_invalid_examples(root: Path, now: datetime) -> list[Finding]:
    """Every examples/invalid/manifest.json case must fail with its declared code."""
    findings: list[Finding] = []
    manifest_path = root / "examples" / "invalid" / "manifest.json"
    if not manifest_path.is_file():
        findings.append(Finding("examples/invalid", "missing_manifest", "examples/invalid/manifest.json not found"))
        return findings

    try:
        manifest = schema_support.load_json(manifest_path)
    except schema_support.JsonLoadError as error:
        findings.append(Finding("examples/invalid", "load_error", str(error)))
        return findings

    cases = manifest.get("cases") if isinstance(manifest, dict) else None
    if not isinstance(cases, list):
        findings.append(Finding("examples/invalid", "malformed_manifest", "manifest.json has no 'cases' array"))
        return findings

    for case in cases:
        if not isinstance(case, dict):
            continue
        case_id = case.get("id", "<unknown>")
        kind = case.get("kind")
        expected_code = case.get("expected_code")
        artifact_rel = case.get("artifact")
        if not isinstance(artifact_rel, str):
            findings.append(Finding("examples/invalid", "malformed_case", f"{case_id}: missing 'artifact'"))
            continue
        artifact_path = (manifest_path.parent / artifact_rel).resolve()

        if kind == "security":
            codes = {f.code for f in security_scan.scan_tree(artifact_path.parent)}
        else:
            try:
                instance = schema_support.load_json(artifact_path)
            except schema_support.JsonLoadError as error:
                findings.append(Finding("examples/invalid", "load_error", f"{case_id}: {error}"))
                continue
            if kind == "contract":
                schema = _load_schema_by_id(root, "adapter-contract")
                codes = {f.code for f in validate_contract.evaluate(instance, schema)}
            elif kind == "source":
                schema = _load_schema_by_id(root, "source-assessment")
                codes = {f.code for f in assess_source.evaluate(instance, schema)}
            elif kind == "fixture":
                schema = _load_schema_by_id(root, "fixture-manifest")
                codes = {f.code for f in validate_fixture.evaluate(instance, schema, artifact_path)}
            elif kind == "freshness":
                codes = {f.code for f in check_freshness.evaluate(instance, now)}
            else:
                findings.append(Finding("examples/invalid", "unknown_kind", f"{case_id}: unrecognized kind {kind!r}"))
                continue

        if expected_code not in codes:
            findings.append(
                Finding(
                    "examples/invalid",
                    "rejection_mismatch",
                    f"{case_id}: expected code {expected_code!r}, validator produced {sorted(codes)!r}",
                )
            )

    return findings


def _check_security(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for scan_finding in security_scan.scan_tree(root):
        if any(scan_finding.path.startswith(prefix) for prefix in _SECURITY_SCAN_PATH_EXCLUDES):
            continue
        findings.append(Finding("security", scan_finding.code, f"{scan_finding.path}:{scan_finding.line}: {scan_finding.message}"))
    return findings


def _check_eval_validator(root: Path) -> list[Finding]:
    """Run the eval validator in a fresh interpreter."""
    run_evals_path = root / "scripts" / "run_evals.py"
    if not run_evals_path.is_file():
        return []

    result = subprocess.run(
        [sys.executable, str(run_evals_path), "--validate", str(root)],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode == 0:
        return []
    detail = (result.stdout + result.stderr).strip()
    return [Finding("evals", "eval_issue", detail or f"exit {result.returncode}")]


def run_all(root: Path, *, now: datetime | None = None) -> list[Finding]:
    """Run every orchestration stage and return the combined findings."""
    resolved_now = now if now is not None else datetime.now(timezone.utc)
    findings: list[Finding] = []
    findings.extend(_check_structure(root))
    findings.extend(_check_schema_conformance(root, "templates"))
    findings.extend(_check_schema_conformance(root, "examples/valid"))
    findings.extend(_check_valid_examples_semantics(root, resolved_now))
    findings.extend(_check_drift_tool(root))
    findings.extend(_check_invalid_examples(root, resolved_now))
    findings.extend(_check_eval_validator(root))
    findings.extend(_check_security(root))
    return findings


# --- CLI -------------------------------------------------------------------


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="validate.py",
        description=(
            "Validate the League API Engineering package end to end: structure, schemas, "
            "examples, every focused validator, the eval suite (if present), and the security scan."
        ),
    )
    parser.add_argument("root", nargs="?", type=Path, default=Path("."), help="package root (default: .)")
    parser.add_argument("--json", action="store_true", help="emit findings as JSON")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    root = args.root.resolve()

    if not (root / "schemas").is_dir():
        print(f"NOT_A_PACKAGE_ROOT: no schemas/ directory under {root}", file=sys.stderr)
        return 2

    findings = run_all(root)

    if args.json:
        payload = {
            "ok": not findings,
            "root": str(root),
            "issues": [f._asdict() for f in findings],
        }
        print(json.dumps(payload, sort_keys=True))
    else:
        for finding in findings:
            print(f"{finding.stage}:{finding.code} {finding.message}", file=sys.stderr)
        if findings:
            print(f"PACKAGE_INVALID: {len(findings)} issue(s) under {root}", file=sys.stderr)
        else:
            print(f"PACKAGE_VALID: {root}")

    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
