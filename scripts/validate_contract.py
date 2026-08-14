#!/usr/bin/env python3
"""Validate an ``adapter-contract`` artifact beyond bare schema conformance.

Schema conformance is delegated to ``schema_support``. On top of that this
script checks semantics the schema's declarative subset cannot express:

- **Cache dimensions:** no duplicate ``key_dimensions`` entries, the cache
  key always carries ``adapter_id``, and every ``invalidation`` trigger
  that implies a dimension (``patch_change`` -> ``patch``, etc.) has that
  dimension present in ``key_dimensions``.
- **Provenance:** ``retrieved_at`` is always tracked, and any non
  first-party source also tracks ``source_id``/``evidence_class`` so
  consumers can attribute and trust-weight the data.
- **Fallback compatibility/attribution/population:** a fallback marked
  incompatible must not be described as served automatically or silently;
  a fallback marked compatible must not carry placeholder attribution or
  population text; a fallback must not reference its own adapter.
- **Auth and secret rules:** ``authentication.mode`` and
  ``authentication.secret_source`` must agree, and ``loopback_tls_only``
  may only be set when every source URL is actually a loopback host.

Standard library only. No network access.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, NamedTuple
from urllib.parse import urlsplit

import schema_support

SCHEMA_ID = "adapter-contract"
SCHEMA_FILE = "adapter-contract.schema.json"

# invalidation trigger -> the cache-key dimension it implies must exist.
_INVALIDATION_REQUIRES_DIMENSION: dict[str, str] = {
    "patch_change": "patch",
    "locale_change": "locale",
    "queue_change": "queue",
    "region_change": "region",
}

# authentication.mode -> the only secret_source that makes sense for it.
_MODE_EXPECTS_SECRET_SOURCE: dict[str, str] = {
    "none": "none",
    "runtime_env": "environment",
    "local_client_runtime": "local_client",
    "user_supplied": "user_input",
}

_SILENT_FALLBACK_WORDS = ("silent", "automatic", "transparent", "without notice", "without disclosure", "by default")
_PLACEHOLDER_VALUES = {"unknown", "n/a", "na", "tbd", "todo", "none", "placeholder", "fixme", "?"}
_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


class Finding(NamedTuple):
    path: str
    code: str
    message: str


def _check_cache(instance: dict[str, Any], findings: list[Finding]) -> None:
    cache = instance.get("cache")
    if not isinstance(cache, dict):
        return
    dimensions = cache.get("key_dimensions")
    if not isinstance(dimensions, list):
        return

    seen: set[str] = set()
    for dimension in dimensions:
        if dimension in seen:
            findings.append(Finding("$.cache.key_dimensions", "cache_key", f"duplicate cache-key dimension {dimension!r}"))
        seen.add(dimension)

    if "adapter_id" not in dimensions:
        findings.append(
            Finding("$.cache.key_dimensions", "cache_key", "cache key must include 'adapter_id' to avoid cross-adapter collisions")
        )

    invalidation = cache.get("invalidation")
    if isinstance(invalidation, list):
        for trigger in invalidation:
            required = _INVALIDATION_REQUIRES_DIMENSION.get(trigger)
            if required and required not in dimensions:
                findings.append(
                    Finding(
                        "$.cache.key_dimensions",
                        "cache_key",
                        f"invalidation trigger {trigger!r} requires dimension {required!r} in key_dimensions",
                    )
                )


def _check_provenance(instance: dict[str, Any], findings: list[Finding]) -> None:
    normalization = instance.get("normalization")
    if not isinstance(normalization, dict):
        return
    fields = normalization.get("provenance_fields")
    if not isinstance(fields, list):
        return

    if "retrieved_at" not in fields:
        findings.append(
            Finding("$.normalization.provenance_fields", "provenance", "provenance_fields must track 'retrieved_at' for freshness")
        )

    source = instance.get("source")
    authority = source.get("authority") if isinstance(source, dict) else None
    if authority is not None and authority != "first_party":
        for required in ("source_id", "evidence_class"):
            if required not in fields:
                findings.append(
                    Finding(
                        "$.normalization.provenance_fields",
                        "provenance",
                        f"non first-party source ({authority!r}) must track {required!r} in provenance_fields",
                    )
                )


def _check_fallbacks(instance: dict[str, Any], findings: list[Finding]) -> None:
    fallbacks = instance.get("fallbacks")
    if not isinstance(fallbacks, list):
        return
    own_adapter_id = instance.get("adapter_id")

    for index, fallback in enumerate(fallbacks):
        if not isinstance(fallback, dict):
            continue
        path = f"$.fallbacks[{index}]"

        if own_adapter_id is not None and fallback.get("adapter_id") == own_adapter_id:
            findings.append(Finding(path, "incompatible_fallback", "a fallback must not reference its own adapter_id"))

        compatible = fallback.get("compatible")
        reason = str(fallback.get("reason", ""))
        attribution = str(fallback.get("attribution", ""))
        population = str(fallback.get("population", ""))
        haystack = f"{reason} {attribution}".lower()

        if compatible is False:
            hit = next((word for word in _SILENT_FALLBACK_WORDS if word in haystack), None)
            if hit is not None:
                findings.append(
                    Finding(
                        path,
                        "incompatible_fallback",
                        f"fallback is marked incompatible but reason/attribution implies it is still served ({hit!r})",
                    )
                )
        elif compatible is True:
            if attribution.strip().lower() in _PLACEHOLDER_VALUES:
                findings.append(Finding(path, "incompatible_fallback", "compatible fallback has placeholder attribution"))
            if population.strip().lower() in _PLACEHOLDER_VALUES:
                findings.append(Finding(path, "incompatible_fallback", "compatible fallback has placeholder population"))


def _check_auth(instance: dict[str, Any], findings: list[Finding]) -> None:
    authentication = instance.get("authentication")
    if not isinstance(authentication, dict):
        return

    mode = authentication.get("mode")
    secret_source = authentication.get("secret_source")
    expected = _MODE_EXPECTS_SECRET_SOURCE.get(mode)
    if expected is not None and secret_source != expected:
        findings.append(
            Finding(
                "$.authentication.secret_source",
                "auth",
                f"mode {mode!r} expects secret_source {expected!r}, found {secret_source!r}",
            )
        )

    if authentication.get("loopback_tls_only") is True:
        source = instance.get("source")
        urls = source.get("urls") if isinstance(source, dict) else None
        if isinstance(urls, list):
            for url in urls:
                host = urlsplit(str(url)).hostname
                if host is None or host.lower() not in _LOOPBACK_HOSTS:
                    findings.append(
                        Finding(
                            "$.source.urls",
                            "loopback_tls",
                            f"loopback_tls_only is true but source URL {url!r} is not a loopback host",
                        )
                    )


def evaluate(instance: Any, schema: Any) -> list[Finding]:
    """Schema-validate ``instance`` and apply adapter-contract semantics."""
    findings: list[Finding] = []

    for issue in schema_support.validate_instance(instance, schema):
        findings.append(Finding(issue.path, "schema", issue.render()))

    if not isinstance(instance, dict):
        return findings

    _check_cache(instance, findings)
    _check_provenance(instance, findings)
    _check_fallbacks(instance, findings)
    _check_auth(instance, findings)

    return findings


# --- CLI -------------------------------------------------------------------


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="validate_contract.py",
        description="Validate an adapter-contract artifact: schema plus cache/provenance/fallback/auth semantics.",
    )
    parser.add_argument("path", type=Path, help="adapter-contract JSON artifact")
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
            print(f"ADAPTER_CONTRACT_INVALID: {args.path}", file=sys.stderr)
        else:
            print(f"ADAPTER_CONTRACT_VALID: {args.path}")

    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
