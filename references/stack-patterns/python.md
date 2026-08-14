# Python production patterns

Use typed values, capability-separated transports, and explicit policy gates for League adapters. Standard-library code can express the safety boundary even when a production HTTP library supplies the transport implementation.

## Typed failures and normalized provenance

```python
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Generic, TypeVar


class ErrorClass(str, Enum):
    OFFLINE = "offline"
    UNAUTHORIZED = "unauthorized"
    RATE_LIMITED = "rate_limited"
    NOT_FOUND = "not_found"
    NO_DATA = "no_data"
    UNSUPPORTED_CONTEXT = "unsupported_context"
    TRANSPORT = "transport"
    HTTP_STATUS = "http_status"
    PARSE = "parse"
    SCHEMA_DRIFT = "schema_drift"
    POLICY_BLOCKED = "policy_blocked"


class EvidenceClass(str, Enum):
    VERIFIED_CURRENT = "verified-current"
    OBSERVED_UNDOCUMENTED = "observed-undocumented"
    HISTORICAL = "historical"
    INFERENCE = "inference"


@dataclass(frozen=True)
class AdapterError(Exception):
    error_class: ErrorClass
    message: str
    status: int | None = None
    retry_after_seconds: int | None = None


@dataclass(frozen=True)
class Provenance:
    source_id: str
    endpoint_family: str
    evidence: EvidenceClass
    observed_at: str
    patch: str | None = None
    population: str | None = None


T = TypeVar("T")


@dataclass(frozen=True)
class Sourced(Generic[T]):
    value: T
    provenance: Provenance
```

Treat an empty valid response as `NO_DATA`. Preserve provenance through normalization. In particular, aggregate build data must retain provider, patch, region, tier, queue, lane, and sample-window population instead of converting materially different populations into one unlabeled fallback.

## Isolate loopback TLS from remote traffic

```python
from dataclasses import dataclass
from ipaddress import ip_address
from typing import Protocol


@dataclass(frozen=True)
class LoopbackEndpoint:
    host: str
    port: int
    password: str

    @classmethod
    def from_input(cls, host: str, port: int, password: str) -> "LoopbackEndpoint":
        allowed = host == "localhost" or (ip_address(host).is_loopback if host else False)
        if not allowed:
            raise AdapterError(ErrorClass.POLICY_BLOCKED, "certificate exception is loopback-only")
        if not 1 <= port <= 65535 or not password:
            raise AdapterError(ErrorClass.PARSE, "invalid loopback connection metadata")
        return cls(host=host, port=port, password=password)


class RemoteTransport(Protocol):
    def get(self, url: str, authorization: str) -> bytes: ...


class LoopbackTransport(Protocol):
    def get(self, endpoint: LoopbackEndpoint, path: str) -> bytes: ...
```

Only `LoopbackTransport` may use an isolated certificate exception after `LoopbackEndpoint.from_input` validates the destination. `RemoteTransport` validates ordinary HTTPS certificates and cannot accept an LCU password. Do not disable TLS verification globally, reuse a permissive SSL context for remote URLs, or log passwords, authorization values, cookies, tokens, or identifying response data.

## Keep routing separate from authentication

```python
from enum import Enum
from urllib.parse import quote


class PlatformRoute(str, Enum):
    NA1 = "na1"
    EUW1 = "euw1"
    KR = "kr"


class RegionalRoute(str, Enum):
    AMERICAS = "americas"
    EUROPE = "europe"
    ASIA = "asia"
    SEA = "sea"


def match_regional_route(platform: PlatformRoute) -> RegionalRoute:
    return {
        PlatformRoute.NA1: RegionalRoute.AMERICAS,
        PlatformRoute.EUW1: RegionalRoute.EUROPE,
        PlatformRoute.KR: RegionalRoute.ASIA,
    }[platform]


def match_ids_url(route: RegionalRoute, puuid_input: str) -> str:
    return f"https://{route.value}.api.riotgames.com/lol/match/v5/matches/by-puuid/{quote(puuid_input, safe='')}/ids"
```

Routing derives from the requested platform, while authorization is injected at an approved trusted boundary. Never embed a production Riot key in a desktop distributable. A local-only product that cannot use a trusted backend must reject remote account-data functionality that requires server-side credentials.

## Bounded retry and complete cache keys

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class CacheKey:
    source_id: str
    endpoint_family: str
    subject_id: str
    patch: str | None = None
    locale: str | None = None
    region: str | None = None
    queue: str | None = None
    lane: str | None = None
    tier: str | None = None
    sample_window: str | None = None


def retry_delay_seconds(error: AdapterError, attempt: int) -> int | None:
    if attempt >= 3:
        return None
    if error.error_class in {ErrorClass.OFFLINE, ErrorClass.TRANSPORT}:
        return 2**attempt
    if error.error_class is ErrorClass.RATE_LIMITED:
        return error.retry_after_seconds if error.retry_after_seconds is not None else 2 ** (attempt + 1)
    if error.error_class is ErrorClass.HTTP_STATUS and error.status is not None and 500 <= error.status <= 599:
        return 2**attempt
    return None
```

Retry only transient network, rate-limit, and selected server-failure outcomes. Never retry `UNAUTHORIZED`, `PARSE`, `SCHEMA_DRIFT`, `POLICY_BLOCKED`, `UNSUPPORTED_CONTEXT`, `NOT_FOUND`, or `NO_DATA` in a blind loop. Include all response-changing dimensions in cache keys and define TTL, stale behavior, and invalidation per endpoint.

## Sanitized fixture tests and optional canaries

```python
import json
import unittest


def parse_champion_fixture(input_text: str) -> dict[str, str]:
    try:
        value = json.loads(input_text)
    except json.JSONDecodeError as error:
        raise AdapterError(ErrorClass.PARSE, "invalid champion fixture") from error
    if not isinstance(value, dict) or not isinstance(value.get("id"), str) or not isinstance(value.get("name"), str):
        raise AdapterError(ErrorClass.PARSE, "invalid champion fixture")
    return {"id": value["id"], "name": value["name"]}


class FixtureTests(unittest.TestCase):
    def test_parses_sanitized_fixture(self) -> None:
        self.assertEqual(parse_champion_fixture('{"id":"Aatrox","name":"Aatrox"}')["id"], "Aatrox")
```

Fixtures contain only sanitized static values, not LCU credentials, API keys, bearer tokens, PUUIDs, summoner names, or real histories. An optional canary is separately invoked by an operator, never required in ordinary tests, and must classify a changed documented shape as `SCHEMA_DRIFT`; it must not hide the change by accepting arbitrary unknown fields.
