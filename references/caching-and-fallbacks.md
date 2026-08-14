# Caching and fallbacks

Cache and fallback behavior are part of the data contract. They must preserve what the product claims about source, population, version, freshness, and availability.

## Cache contract

A cache key includes every dimension that can alter normalized meaning. Select only relevant dimensions, but document omissions:

```text
source + endpoint-family + normalization-version + schema-id + patch/version
+ locale + platform/region + queue/lane/tier + query identity + access scope
```

Do not share a cache entry across different source populations, patches, locales, routes, user/account scopes, or normalizer versions merely because a display label matches.

For every entry define:

- creation/observation time and expiry time;
- TTL rationale and maximum stale window;
- validators/fingerprints and revalidation conditions;
- invalidation triggers: patch/version, locale mapping, schema, provider methodology, auth scope, policy/terms, or product semantic changes;
- persistence boundary, encryption/access control where appropriate, and retention/deletion policy;
- offline behavior and user-visible stale label.

Static versioned data may have a long TTL when its version is pinned. Local live state has a short or session-only lifetime. Remote account/match data and aggregate provider data require source-specific freshness rules. Do not assign one universal TTL.

## Stale data

Serving stale data is permitted only when the adapter contract says it preserves the feature safely. The normalized result must carry actual observed version/time and `stale: true`. Never relabel stale data as live/current or keep it after a policy, schema, or semantic incompatibility invalidates it.

Stale data is not a fallback for `unauthorized`, `policy_blocked`, `parse`, or `schema_drift` unless a separately reviewed snapshot remains safe and clearly labeled. When in doubt, hide the result.

## Retry policy

Retry only bounded, idempotent operations that have a credible transient cause:

| Class | Retry default | Notes |
|---|---|---|
| `offline`, `transport` | Bounded | Cancellation, timeout, jitter, and lifecycle awareness required |
| `rate_limited` | Bounded | Follow documented headers; do not amplify load |
| selected `http_status` | Bounded | Only when source-specific policy classifies it transient |
| `unauthorized`, `not_found`, `no_data`, `unsupported_context`, `parse`, `schema_drift`, `policy_blocked` | Never blind-retry | Correct credentials/context/schema/policy first |

Retries must have a maximum attempt count, total deadline, backoff/jitter policy, cancellation path, and sanitized observability. A missing local client or ended game must stop the loop.

## Fallback decision

A fallback is valid only after a field-by-field and semantic comparison with the primary source. Evaluate authority, permission, population, source method, version/patch, region/platform, locale, queue/lane/tier, timestamps, units, no-data semantics, attribution, and UI claim.

| Decision | Meaning | UI/provenance behavior |
|---|---|---|
| `compatible` | Semantics materially match | Retain source identity and fallback event |
| `compatible_with_label` | Useful but material differences exist | Explicitly identify alternate source and differences |
| `blocked` | Differences/terms make substitution misleading or forbidden | Return original failure or no result |

Do not use “best effort” as an excuse to collapse populations or hide stale/alternate provenance.

## Safe fallback examples

- A validated cached copy of the same pinned static version may serve during a brief outage when labeled with its version and age.
- A provider’s documented regional result may fall back to its documented global result only if the product labels the population change and the contract permits it.
- An active-game feature has no acceptable remote fallback when local live data is unavailable; return `unsupported_context` rather than fabricate live state.

## Observability

Record aggregate, sanitized counts for cache hit/miss, stale-serving, fallback decision, retry exhaustion, and drift blocks. Never log credentials, cookies, LCU passwords, raw player histories, or payloads solely to explain a cache miss.
