#!/usr/bin/env python3
"""Recursive text-file scanner for League API Engineering package content.

Flags Riot/LCU secrets, generic auth tokens/cookies, user-identifying
absolute paths, remote insecure-TLS relaxation, unsafe local-client
techniques, and textual phrasing describing an undisclosed fallback
substitution.

Every rule is exempted on a line that is itself an educational
prohibition -- i.e. the surrounding text clearly negates the pattern
(a "never do X" style statement). Negation is looked up on the matched
line first, then -- because Markdown often states the prohibition once
and lists violating techniques as a bullet list below it -- on the
nearest preceding non-blank, non-list-item line.

Standard library only. No network access.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Iterable, NamedTuple

# --- Exclusions --------------------------------------------------------------

# Build/cache directories never carry reviewable source content.
#
# ``evals`` is excluded by default too: eval suites intentionally narrate
# adversarial scenarios as prompts to grade, not as shipped implementation
# guidance. Scanning them here would flag a test fixture for describing
# the very behavior it exists to catch. The eval suites have their own
# structural validator (``run_evals.py``); pass ``--include-evals`` to opt
# back into scanning them with this tool.
DEFAULT_EXCLUDED_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "node_modules",
        "dist",
        "build",
        "target",
        ".venv",
        "venv",
        "evals",
    }
)

BINARY_SUFFIXES: frozenset[str] = frozenset(
    {
        ".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp", ".zip", ".pyc",
        ".pdf", ".woff", ".woff2", ".ttf", ".eot", ".exe", ".dll", ".so",
        ".bin", ".pyo",
    }
)

# This module's own rule table below necessarily contains, as literal
# alternation text, the very words/phrases it detects (e.g.
# "ReadProcessMemory" inside a regex alternative, or "silently" in this
# docstring's own prose about the "silent fallback" rule). Scanning this
# file's own rule definitions for the patterns they define is a category
# error -- the same reasoning that excludes evals/ prompts above -- so this
# script never scans itself. Every other file, including every other
# script in this package, is still scanned normally.
_SELF_PATH = Path(__file__).resolve()


class Finding(NamedTuple):
    """One security-scan match with enough context to act on it."""

    path: str
    line: int
    code: str
    message: str


def symlink_finding(path: str) -> Finding:
    """Report a symlink without reading its target."""
    return Finding(path, 0, "symlink", "symlinked content is not scanned")


# --- Negation handling -------------------------------------------------------

_NEGATION_RE = re.compile(
    r"(?i)\b(never|cannot|no|not|reject\w*|prohibit\w*|forbid\w*|"
    r"disallow\w*|avoid\w*|block(?:ed|s|ing)?|refus\w*|without)\b|n't\b"
)
_LIST_ITEM_RE = re.compile(r"^\s*([-*+]|\d+[.)])\s+")


def _is_educational(lines: list[str], index: int, max_lookback: int = 15) -> bool:
    """True when the match at ``lines[index]`` sits in a negated context."""
    if _NEGATION_RE.search(lines[index]):
        return True
    cursor = index
    steps = 0
    while cursor > 0 and steps < max_lookback:
        previous = lines[cursor - 1]
        stripped = previous.strip()
        if stripped == "" or _LIST_ITEM_RE.match(previous):
            cursor -= 1
            steps += 1
            continue
        # First non-blank, non-list-item ancestor: the probable intro
        # sentence for this block. Its own negation (or lack of one)
        # decides the whole block.
        return bool(_NEGATION_RE.search(previous))
    return False


# --- Rule table ---------------------------------------------------------------

_RIOT_KEY_RE = re.compile(r"RGAPI-[A-Za-z0-9-]{10,}")

_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    _RIOT_KEY_RE,
    re.compile(r"(?i)\b(x-riot-token|x-riot-auth|remoting-auth-token)\b\s*[:=]\s*\S{6,}"),
    re.compile(r"(?i)\bauthorization\s*[:=]\s*['\"]?(bearer|basic)\s+\S{6,}"),
    re.compile(
        r"(?i)\b(password|passwd|secret|api[_-]?key|access[_-]?token|client[_-]?secret)"
        r"\s*[:=]\s*['\"][^'\"\s]{6,}['\"]"
    ),
    re.compile(r"(?i)\bcookie\s*[:=]\s*[^=\s]+=\S+"),
)

_USER_PATH_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b[A-Za-z]:(?:\\\\|\\)Users(?:\\\\|\\)[^\\\\/\s\"']+(?=(?:\\\\|\\|[/\s\"']|$))", re.IGNORECASE),
    re.compile(r"(?<![\w~])/(?:home|Users)/[^/\s\"']+(?=[/\s\"']|$)"),
)

_REMOTE_TLS_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)danger_accept_invalid_certs\s*[:=(]?\s*true"),
    re.compile(r"(?i)\bverify\s*=\s*False\b"),
    re.compile(r"(?i)rejectUnauthorized\s*:\s*false"),
    re.compile(r"(?i)insecureskipverify\s*[:=]?\s*true"),
    re.compile(r"NODE_TLS_REJECT_UNAUTHORIZED\s*=\s*['\"]?0"),
    re.compile(r"(?i)ssl_verify\s*=\s*false"),
    re.compile(r"\bSSL_VERIFY_NONE\b"),
)

_UNSAFE_TECHNIQUE_RE = re.compile(
    r"(?i)\b(ReadProcessMemory|WriteProcessMemory|CreateRemoteThread|SetWindowsHookEx|"
    r"dll injection|process injection|code injection|memory (?:scan\w*|read\w*)|"
    r"process[- ]memory|anti[- ]cheat (?:bypass\w*|interference|circumvent\w*)|"
    r"hidden[- ]state (?:extraction|inference)|packet (?:interception|injection|capture)|"
    r"injects? a hook|hooks? (?:into|the) (?:the )?(?:game|client) process|"
    r"in[- ]memory game state)\b"
)

_SILENT_FALLBACK_RE = re.compile(r"(?i)\bsilently\b")


def scan_text(text: str, label: str) -> list[Finding]:
    """Scan one document's text content; ``label`` becomes the finding path."""
    findings: list[Finding] = []
    lines = text.splitlines()
    for index, line in enumerate(lines):
        line_no = index + 1
        for pattern in _SECRET_PATTERNS:
            match = pattern.search(line)
            if match:
                findings.append(
                    Finding(label, line_no, "secret", f"possible embedded secret: {match.group(0)!r}")
                )
        for pattern in _USER_PATH_PATTERNS:
            match = pattern.search(line)
            if match:
                findings.append(
                    Finding(label, line_no, "user_path", f"user-identifying absolute path: {match.group(0)!r}")
                )
        for pattern in _REMOTE_TLS_PATTERNS:
            match = pattern.search(line)
            if match:
                findings.append(
                    Finding(label, line_no, "remote_tls", f"remote TLS verification relaxed: {match.group(0)!r}")
                )
        match = _UNSAFE_TECHNIQUE_RE.search(line)
        if match and not _is_educational(lines, index):
            findings.append(
                Finding(label, line_no, "unsafe_technique", f"unsafe local-client technique: {match.group(0)!r}")
            )
        match = _SILENT_FALLBACK_RE.search(line)
        if match and not _is_educational(lines, index):
            findings.append(
                Finding(label, line_no, "silent_fallback", "possible silent/undisclosed fallback substitution")
            )
    return findings


def _is_probably_text(path: Path) -> bool:
    return path.suffix.lower() not in BINARY_SUFFIXES


def scan_tree(
    root: Path,
    *,
    exclude_dirs: frozenset[str] | None = None,
    include_evals: bool = False,
) -> list[Finding]:
    """Recursively scan every text file under ``root``."""
    excluded = set(DEFAULT_EXCLUDED_DIRS if exclude_dirs is None else exclude_dirs)
    if include_evals:
        excluded.discard("evals")
    root = root.resolve()
    findings: list[Finding] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            relative = path.relative_to(root)
            findings.append(symlink_finding(relative.as_posix()))
            continue
        if not path.is_file():
            continue
        if path == _SELF_PATH:
            continue
        relative = path.relative_to(root)
        if any(part in excluded for part in relative.parts):
            continue
        if not _is_probably_text(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        findings.extend(scan_text(text, relative.as_posix()))
    return findings


# --- CLI -----------------------------------------------------------------------


def _render_text(findings: Iterable[Finding]) -> None:
    for finding in findings:
        print(f"{finding.code} {finding.path}:{finding.line}: {finding.message}", file=sys.stderr)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="security_scan.py",
        description=(
            "Recursively scan text files for secrets, user paths, insecure TLS, "
            "unsafe local-client techniques, and undisclosed-fallback phrasing."
        ),
    )
    parser.add_argument("root", nargs="?", type=Path, default=Path("."), help="directory to scan (default: .)")
    parser.add_argument(
        "--exclude", action="append", default=[], metavar="DIR",
        help="additional directory name to exclude (repeatable)",
    )
    parser.add_argument(
        "--include-evals", action="store_true",
        help="also scan the evals/ suites (off by default; see module docstring)",
    )
    parser.add_argument("--json", action="store_true", help="emit findings as JSON")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    root: Path = args.root
    if not root.is_dir():
        print(f"NOT_A_DIRECTORY: {root}", file=sys.stderr)
        return 2

    exclude_dirs = DEFAULT_EXCLUDED_DIRS | set(args.exclude)
    findings = scan_tree(root, exclude_dirs=exclude_dirs, include_evals=args.include_evals)

    if args.json:
        payload = {
            "ok": not findings,
            "root": str(root),
            "issues": [f._asdict() for f in findings],
        }
        print(json.dumps(payload, sort_keys=True))
    else:
        _render_text(findings)
        if findings:
            print(f"SECURITY_ISSUES: {len(findings)} finding(s) under {root}", file=sys.stderr)
        else:
            print(f"SECURITY_CLEAN: {root}")

    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
