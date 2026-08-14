#!/usr/bin/env python3
"""Deterministic, offline structural validator and inventory tool for the
league-api-engineering eval suites.

This harness never calls an LLM or the network. It only reads the paired
Markdown+JSON suites under ``evals/`` and checks that their structure matches
the package's documented mode, evidence-class, and error-class vocabulary
(see ``SKILL.md``). Running actual cases against a model is out of scope for
this script.

Usage:
    python scripts/run_evals.py --validate [root]
    python scripts/run_evals.py --list [root]

``root`` is optional and may point at the package root (the directory that
contains ``evals/``) or at the ``evals`` directory itself. It defaults to
this script's own package root.

Exit codes:
    0  success (validation clean, or listing completed)
    1  content problem (validation issues found, or a suite failed to load)
    2  usage or structural error (no ``evals`` directory could be found)
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# --- Public vocabulary -----------------------------------------------------
# Kept in sync with SKILL.md. A case is invalid if it uses a mode, evidence
# class, or error class outside these sets.

SUPPORTED_MODES: frozenset[str] = frozenset(
    {"implement", "audit", "debug", "research", "policy"}
)

SUPPORTED_EVIDENCE_CLASSES: frozenset[str] = frozenset(
    {"verified-current", "observed-undocumented", "historical", "inference"}
)

SUPPORTED_ERROR_CLASSES: frozenset[str] = frozenset(
    {
        "offline",
        "unauthorized",
        "rate_limited",
        "not_found",
        "no_data",
        "unsupported_context",
        "transport",
        "http_status",
        "parse",
        "schema_drift",
        "policy_blocked",
    }
)

# The exact suite set the package must ship, in documented order.
REQUIRED_SUITE_IDS: tuple[str, ...] = (
    "source-selection",
    "implementation",
    "debugging",
    "policy",
    "adversarial",
)

# Every adversarial holdout category that must be exercised by at least one
# case in the adversarial suite. Membership is declared through that case's
# existing ``coverage`` array (the same field every other suite already uses
# to tag its topics), so no new schema field is introduced.
REQUIRED_ADVERSARIAL_CATEGORIES: frozenset[str] = frozenset(
    {
        "embedded_keys",
        "remote_tls_relaxation",
        "blind_retries",
        "terms_free_scraping",
        "silent_population_changes",
        "mmr_estimation",
        "hidden_state",
        "exclusive_fullscreen_injection",
    }
)


# --- Issue reporting ---------------------------------------------------------


@dataclass(frozen=True)
class Issue:
    """One deterministic validation failure, sortable for stable output."""

    suite: str
    case_id: str
    message: str

    def sort_key(self) -> tuple[str, str, str]:
        return (self.suite, self.case_id, self.message)

    def render(self) -> str:
        location = f"{self.suite}:{self.case_id}" if self.case_id else self.suite
        return f"{location}: {self.message}"


class SuiteLoadError(Exception):
    """Raised when a suite's JSON document cannot be parsed at all."""


# --- Loading -----------------------------------------------------------------


def _resolve_evals_dir(root: Path) -> Path:
    """Return the ``evals`` directory for a package-root or evals-dir path."""
    if root.name == "evals" and root.is_dir():
        return root
    return root / "evals"


def default_root() -> Path:
    """The package root that ships this script (``scripts/..``)."""
    return Path(__file__).resolve().parent.parent


def _is_nonempty_str(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _load_json_document(path: Path) -> Any:
    """Load one JSON file, raising ``SuiteLoadError`` with a clear reason."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise SuiteLoadError(f"cannot read {path}: {error}") from error
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise SuiteLoadError(f"invalid JSON in {path}: {error}") from error


# --- Case-level structure -----------------------------------------------------


@dataclass(frozen=True)
class CaseSummary:
    """Minimal fields needed for listing and cross-suite checks."""

    id: str
    mode: str
    coverage: tuple[str, ...]


def _validate_criterion(
    criterion: Any, suite: str, case_id: str, index: int, issues: list[Issue]
) -> None:
    prefix = f"criteria[{index}]"
    if not isinstance(criterion, dict):
        issues.append(Issue(suite, case_id, f"{prefix} must be an object"))
        return
    if not _is_nonempty_str(criterion.get("id")):
        issues.append(Issue(suite, case_id, f"{prefix}.id must be a nonempty string"))
    if not _is_nonempty_str(criterion.get("statement")):
        issues.append(
            Issue(suite, case_id, f"{prefix}.statement must be a nonempty string")
        )
    if not isinstance(criterion.get("expected"), bool):
        issues.append(Issue(suite, case_id, f"{prefix}.expected must be a boolean"))


def _validate_class_array(
    value: Any,
    allowed: frozenset[str],
    field: str,
    suite: str,
    case_id: str,
    issues: list[Issue],
) -> None:
    """Validate a nonempty, duplicate-free array of strings drawn from ``allowed``."""
    if not isinstance(value, list) or not value:
        issues.append(Issue(suite, case_id, f"{field} must be a nonempty array"))
        return
    seen: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, str):
            issues.append(Issue(suite, case_id, f"{field}[{index}] must be a string"))
            continue
        if item in seen:
            issues.append(
                Issue(suite, case_id, f"{field}[{index}] duplicates {item!r}")
            )
            continue
        seen.add(item)
        if item not in allowed:
            issues.append(
                Issue(
                    suite,
                    case_id,
                    f"{field}[{index}] {item!r} is not a supported value "
                    f"(expected one of {sorted(allowed)})",
                )
            )


def _validate_string_list(
    value: Any, field: str, suite: str, case_id: str, issues: list[Issue]
) -> tuple[str, ...]:
    """Validate a nonempty array of nonempty strings (no fixed vocabulary)."""
    if not isinstance(value, list) or not value:
        issues.append(Issue(suite, case_id, f"{field} must be a nonempty array"))
        return ()
    result: list[str] = []
    for index, item in enumerate(value):
        if not _is_nonempty_str(item):
            issues.append(
                Issue(suite, case_id, f"{field}[{index}] must be a nonempty string")
            )
            continue
        result.append(item)
    return tuple(result)


def _validate_case(
    case: Any,
    suite: str,
    index: int,
    seen_ids: dict[str, int],
    issues: list[Issue],
) -> CaseSummary:
    """Validate one case object; always returns a best-effort summary."""
    if not isinstance(case, dict):
        issues.append(Issue(suite, "", f"cases[{index}] must be an object"))
        return CaseSummary(id=f"<cases[{index}]>", mode="", coverage=())

    raw_id = case.get("id")
    if not _is_nonempty_str(raw_id):
        issues.append(Issue(suite, "", f"cases[{index}].id must be a nonempty string"))
        case_id = f"<cases[{index}]>"
    else:
        case_id = raw_id
        expected_prefix = f"{suite}."
        if not case_id.startswith(expected_prefix):
            issues.append(
                Issue(suite, case_id, f"id must start with {expected_prefix!r}")
            )
        seen_ids[case_id] = seen_ids.get(case_id, 0) + 1
        if seen_ids[case_id] > 1:
            issues.append(Issue(suite, case_id, "duplicate case id within suite"))

    raw_mode = case.get("mode")
    if raw_mode not in SUPPORTED_MODES:
        issues.append(
            Issue(
                suite,
                case_id,
                f"mode {raw_mode!r} is not one of {sorted(SUPPORTED_MODES)}",
            )
        )
        mode = raw_mode if isinstance(raw_mode, str) else ""
    else:
        mode = raw_mode

    if not _is_nonempty_str(case.get("prompt")):
        issues.append(Issue(suite, case_id, "prompt must be a nonempty string"))

    criteria = case.get("criteria")
    if not isinstance(criteria, list) or not criteria:
        issues.append(Issue(suite, case_id, "criteria must be a nonempty array"))
    else:
        for c_index, criterion in enumerate(criteria):
            _validate_criterion(criterion, suite, case_id, c_index, issues)

    _validate_class_array(
        case.get("expected_evidence_classes"),
        SUPPORTED_EVIDENCE_CLASSES,
        "expected_evidence_classes",
        suite,
        case_id,
        issues,
    )
    _validate_class_array(
        case.get("expected_error_classes"),
        SUPPORTED_ERROR_CLASSES,
        "expected_error_classes",
        suite,
        case_id,
        issues,
    )

    coverage = _validate_string_list(case.get("coverage"), "coverage", suite, case_id, issues)
    _validate_string_list(case.get("tags"), "tags", suite, case_id, issues)

    return CaseSummary(id=case_id, mode=mode, coverage=coverage)


# --- Suite-level structure ----------------------------------------------------


@dataclass(frozen=True)
class SuiteResult:
    """Outcome of loading and validating one suite.

    ``loaded`` means the suite's JSON file parsed as a JSON object -- it does
    not imply every field inside it is valid; content problems are recorded
    as ``Issue`` entries instead so ``--list`` can still enumerate cases from
    a suite that fails ``--validate``.
    """

    suite_id: str
    loaded: bool
    cases: tuple[CaseSummary, ...]


def _validate_suite(evals_dir: Path, suite_id: str, issues: list[Issue]) -> SuiteResult:
    json_path = evals_dir / f"{suite_id}.json"
    md_path = evals_dir / f"{suite_id}.md"

    if not md_path.is_file():
        issues.append(Issue(suite_id, "", f"missing paired suite file {md_path.name}"))
    if not json_path.is_file():
        issues.append(Issue(suite_id, "", f"missing suite file {json_path.name}"))
        return SuiteResult(suite_id, loaded=False, cases=())

    try:
        document = _load_json_document(json_path)
    except SuiteLoadError as error:
        issues.append(Issue(suite_id, "", str(error)))
        return SuiteResult(suite_id, loaded=False, cases=())

    if not isinstance(document, dict):
        issues.append(Issue(suite_id, "", "suite document must be a JSON object"))
        return SuiteResult(suite_id, loaded=False, cases=())

    if not _is_nonempty_str(document.get("schema_version")):
        issues.append(Issue(suite_id, "", "schema_version must be a nonempty string"))
    if document.get("suite_id") != suite_id:
        issues.append(
            Issue(
                suite_id,
                "",
                f"suite_id {document.get('suite_id')!r} must equal {suite_id!r}",
            )
        )
    if not _is_nonempty_str(document.get("title")):
        issues.append(Issue(suite_id, "", "title must be a nonempty string"))

    raw_cases = document.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        issues.append(Issue(suite_id, "", "cases must be a nonempty array"))
        return SuiteResult(suite_id, loaded=True, cases=())

    seen_ids: dict[str, int] = {}
    summaries = tuple(
        _validate_case(case, suite_id, index, seen_ids, issues)
        for index, case in enumerate(raw_cases)
    )
    return SuiteResult(suite_id, loaded=True, cases=summaries)


# --- Cross-suite checks --------------------------------------------------------


def _check_exact_suite_set(evals_dir: Path, issues: list[Issue]) -> None:
    """Flag any suite file present that is not part of the required set."""
    required = set(REQUIRED_SUITE_IDS)
    present_json = {path.stem for path in evals_dir.glob("*.json")}
    present_md = {path.stem for path in evals_dir.glob("*.md")}
    for stem in sorted(present_json - required):
        issues.append(
            Issue(stem, "", f"unexpected suite file {stem}.json is not in the required suite set")
        )
    for stem in sorted(present_md - required):
        issues.append(
            Issue(stem, "", f"unexpected suite file {stem}.md is not in the required suite set")
        )


def _check_global_unique_ids(results: dict[str, SuiteResult], issues: list[Issue]) -> None:
    """Flag a case id reused across suites (within-suite dupes are caught earlier)."""
    owners: dict[str, list[str]] = {}
    for suite_id, result in results.items():
        for case in result.cases:
            owners.setdefault(case.id, []).append(suite_id)
    for case_id, suites in sorted(owners.items()):
        if len(suites) > 1:
            issues.append(
                Issue(
                    "<global>",
                    case_id,
                    f"case id is reused across suites: {sorted(set(suites))}",
                )
            )


def _check_adversarial_categories(results: dict[str, SuiteResult], issues: list[Issue]) -> None:
    """Flag any required adversarial holdout category missing from the suite."""
    adversarial = results.get("adversarial")
    if adversarial is None or not adversarial.loaded:
        return  # already reported as a missing/unloadable suite
    seen: set[str] = set()
    for case in adversarial.cases:
        seen.update(case.coverage)
    for category in sorted(REQUIRED_ADVERSARIAL_CATEGORIES - seen):
        issues.append(
            Issue("adversarial", "", f"missing required adversarial category: {category}")
        )


# --- Public collection entry point --------------------------------------------


def collect(root: Path) -> tuple[dict[str, SuiteResult], list[Issue]]:
    """Load and structurally validate every required suite under ``root``.

    Returns a mapping of suite id to its ``SuiteResult`` (always containing
    all of ``REQUIRED_SUITE_IDS`` as keys) plus the full, unsorted issue list.
    A single ``Issue(suite="<evals>", ...)`` entry means the evals directory
    itself could not be found; every suite is reported unloaded in that case.
    """
    issues: list[Issue] = []
    evals_dir = _resolve_evals_dir(root)

    if not evals_dir.is_dir():
        issues.append(Issue("<evals>", "", f"evals directory not found at {evals_dir}"))
        return {
            suite_id: SuiteResult(suite_id, loaded=False, cases=())
            for suite_id in REQUIRED_SUITE_IDS
        }, issues

    _check_exact_suite_set(evals_dir, issues)

    results: dict[str, SuiteResult] = {
        suite_id: _validate_suite(evals_dir, suite_id, issues)
        for suite_id in REQUIRED_SUITE_IDS
    }

    _check_global_unique_ids(results, issues)
    _check_adversarial_categories(results, issues)

    return results, issues


# --- CLI commands --------------------------------------------------------------


def _evals_dir_missing(issues: list[Issue]) -> bool:
    return any(issue.suite == "<evals>" and issue.case_id == "" for issue in issues)


def _cmd_validate(root: Path) -> int:
    results, issues = collect(root)

    if _evals_dir_missing(issues):
        for issue in sorted(issues, key=Issue.sort_key):
            print(issue.render(), file=sys.stderr)
        print(f"FAIL: evals directory not found under {root}", file=sys.stderr)
        return 2

    if issues:
        for issue in sorted(issues, key=Issue.sort_key):
            print(issue.render(), file=sys.stderr)
        print(f"FAIL: {len(issues)} issue(s) found", file=sys.stderr)
        return 1

    total_cases = sum(len(result.cases) for result in results.values())
    print(f"OK: {len(results)} suites, {total_cases} cases validated")
    return 0


def _cmd_list(root: Path) -> int:
    results, issues = collect(root)

    if _evals_dir_missing(issues):
        print(f"evals directory not found under {root}", file=sys.stderr)
        return 2

    for suite_id in REQUIRED_SUITE_IDS:
        result = results[suite_id]
        if not result.loaded:
            reasons = [
                issue.message
                for issue in issues
                if issue.suite == suite_id and issue.case_id == ""
            ]
            reason = reasons[0] if reasons else "failed to load"
            print(f"{suite_id}: UNAVAILABLE ({reason})")
            continue
        cases = sorted(result.cases, key=lambda case: case.id)
        print(f"{suite_id}: {len(cases)} case(s)")
        for case in cases:
            mode = case.mode or "<invalid-mode>"
            print(f"  {case.id} [{mode}]")

    return 1 if any(not result.loaded for result in results.values()) else 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="run_evals.py",
        description=(
            "Offline structural validator and inventory tool for the "
            "league-api-engineering eval suites. Makes no LLM or network calls."
        ),
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--validate",
        action="store_true",
        help="validate the exact suite set, case ids, vocabulary, and adversarial coverage",
    )
    mode.add_argument(
        "--list",
        action="store_true",
        help="print a deterministic inventory of every suite and case id",
    )
    parser.add_argument(
        "root",
        nargs="?",
        default=None,
        help="package root or evals directory (default: this script's package root)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    root = Path(args.root) if args.root is not None else default_root()

    if args.validate:
        return _cmd_validate(root)
    return _cmd_list(root)


if __name__ == "__main__":
    raise SystemExit(main())
