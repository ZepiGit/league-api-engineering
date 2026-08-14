# TypeScript production patterns

Use discriminated unions and separate transport capabilities so a loopback certificate exception cannot reach remote Riot traffic.

## Typed failures and normalized provenance

```ts
export type ErrorClass =
  | "offline"
  | "unauthorized"
  | "rate_limited"
  | "not_found"
  | "no_data"
  | "unsupported_context"
  | "transport"
  | "http_status"
  | "parse"
  | "schema_drift"
  | "policy_blocked";

export type EvidenceClass =
  | "verified-current"
  | "observed-undocumented"
  | "historical"
  | "inference";

export type AdapterError = {
  class: ErrorClass;
  status?: number;
  retryAfterSeconds?: number;
  message: string;
};

export type Provenance = {
  sourceId: string;
  endpointFamily: string;
  evidence: EvidenceClass;
  observedAt: string;
  patch?: string;
  population?: string;
};

export type Sourced<T> = { value: T; provenance: Provenance };
```

Use `no_data` for a successful response with no applicable result, not for a transport failure. Every normalized aggregate keeps `population` and patch identity so distinct regions, ranks, queues, sample windows, or providers cannot be silently presented as the same statistic.

## Loopback-only TLS client

```ts
import { isIP } from "node:net";

type LoopbackEndpoint = {
  host: "127.0.0.1" | "localhost";
  port: number;
  password: string;
};

type RemoteTransport = {
  get(url: URL, authorization: string): Promise<Response>;
};

type LoopbackTransport = {
  get(endpoint: LoopbackEndpoint, path: string): Promise<Response>;
};

export function makeLoopbackEndpoint(
  host: string,
  port: number,
  password: string,
): LoopbackEndpoint {
  if (host !== "127.0.0.1" && host !== "localhost") {
    throw { class: "policy_blocked", message: "TLS exception is loopback-only" } satisfies AdapterError;
  }
  if (!Number.isInteger(port) || port < 1 || port > 65_535 || password.length === 0) {
    throw { class: "parse", message: "invalid loopback connection metadata" } satisfies AdapterError;
  }
  return { host, port, password };
}
```

The loopback transport may accept the local client certificate only after `makeLoopbackEndpoint` validates the host. The remote transport always verifies certificate chains and has no method that accepts loopback credentials. Never set a process-wide insecure TLS switch. Do not log `password`, Authorization headers, URLs containing credentials, tokens, cookies, or account identifiers.

## Routing is independent of authentication

```ts
export type PlatformRoute = "na1" | "euw1" | "kr";
export type RegionalRoute = "americas" | "europe" | "asia" | "sea";

export function matchRegionalRoute(platform: PlatformRoute): RegionalRoute {
  switch (platform) {
    case "na1": return "americas";
    case "euw1": return "europe";
    case "kr": return "asia";
  }
}

export function matchIdsUrl(route: RegionalRoute, puuid: string): URL {
  return new URL(
    `/lol/match/v5/matches/by-puuid/${encodeURIComponent(puuid)}/ids`,
    `https://${route}.api.riotgames.com`,
  );
}
```

Resolve the platform-to-regional route before request creation. Authentication is injected at a trusted server-side boundary. A shipped desktop application must not contain a production Riot API key; if a feature requires key-bearing remote access and no approved backend exists, return `policy_blocked` or change the feature scope.

## Bounded retry and complete cache keys

```ts
export type CacheKey = Readonly<{
  sourceId: string;
  endpointFamily: string;
  subjectId: string;
  patch?: string;
  locale?: string;
  region?: string;
  queue?: string;
  lane?: string;
  tier?: string;
  sampleWindow?: string;
}>;

export function retryDelaySeconds(error: AdapterError, attempt: number): number | undefined {
  if (attempt >= 3) return undefined;
  if (error.class === "offline" || error.class === "transport") return 2 ** attempt;
  if (error.class === "rate_limited") return error.retryAfterSeconds ?? 2 ** (attempt + 1);
  if (error.class === "http_status" && error.status !== undefined && error.status >= 500 && error.status <= 599) {
    return 2 ** attempt;
  }
  return undefined;
}
```

Retry only `offline`, `transport`, explicit rate limits, and selected `5xx` results. Never blindly retry authorization, parse, schema drift, policy, unsupported-context, not-found, or no-data outcomes. Cache static data by version and locale. Cache aggregate build data by provider, patch, region, tier, lane, queue, and sample window. Define a TTL and stale policy at the call site; do not reuse a cache entry when any response-changing dimension is absent from the key.

## Sanitized fixtures and optional canaries

```ts
import assert from "node:assert/strict";

type ChampionFixture = { id: string; name: string };

export function parseChampionFixture(input: string): ChampionFixture {
  const value: unknown = JSON.parse(input);
  if (typeof value !== "object" || value === null ||
      typeof (value as Record<string, unknown>).id !== "string" ||
      typeof (value as Record<string, unknown>).name !== "string") {
    throw { class: "parse", message: "invalid champion fixture" } satisfies AdapterError;
  }
  return value as ChampionFixture;
}

assert.equal(parseChampionFixture('{"id":"Aatrox","name":"Aatrox"}').id, "Aatrox");
```

Use fixtures with static identifiers only and no tokens, LCU passwords, PUUIDs, summoner names, or match histories. An optional canary runs only from an explicit operator command, uses a public static endpoint or approved credentials outside source control, and classifies an unexpected shape as `schema_drift`. It is never required for normal CI and never automatically retries an incompatible response.
