# Adapter contract

Every source adapter has a reviewable contract before it becomes a product dependency. The contract is the boundary between volatile external/local data and stable product semantics. It must be explicit enough to validate, audit, test, and retire the adapter without guessing.

## Required fields

| Area | Contract requirements |
|---|---|
| Identity | Adapter ID, owner, source class, source/provider identity, endpoint family, status, and review date |
| Evidence | Authority statement, stability expectation, evidence class (`verified-current`, `observed-undocumented`, `historical`, or `inference`), source URLs/observations, and next review trigger |
| Product semantics | User-visible claim; population; patch/version; region/platform; locale; queue/lane/tier; freshness; inclusion/exclusion rules; no-data meaning |
| Access | Auth scheme, key/token custody, local/remote boundary, routing, rate limits, timeout, and allowed retry classes |
| Normalization | Input schema version/fingerprint; normalized schema ID; required/optional fields; units; timestamps; identifiers; provenance fields; unknown-field behavior |
| Failures | Mapping to `offline`, `unauthorized`, `rate_limited`, `not_found`, `no_data`, `unsupported_context`, `transport`, `http_status`, `parse`, `schema_drift`, or `policy_blocked` |
| Cache | Cache-key dimensions, TTL, stale window, validation/revalidation, invalidation trigger, persistence boundary, and offline behavior |
| Fallback | Candidate matrix, compatibility decision, labeling, source transition behavior, and blocked substitutions |
| Assurance | Sanitized fixtures, drift fingerprint, test cases, optional canary, terms/attribution review, privacy/retention decision, and rollback/disable condition |

Schema IDs must be stable relative names, such as `adapter-contract/v1` or `normalized/live-game/v1`, not filesystem paths, user paths, or URLs that cannot be versioned.

## Normalized result envelope

Each adapter should emit a product-neutral envelope conceptually equivalent to:

```text
result = {
  schema_id,
  source: { id, class, authority, evidence_class, retrieved_at },
  context: { version, patch, locale, platform, region, queue, lane, tier },
  freshness: { observed_at, expires_at, stale },
  data,
  error: null | { class, retryable, sanitized_detail }
}
```

The exact machine-readable schema may vary, but these distinctions must survive normalization. A success with an empty collection is not automatically `no_data`; record what the source means. Never return fabricated `data` alongside a blocked or parse/drift failure.

## Error mapping rules

- `offline`: the required local/network environment is unavailable.
- `transport`: a bounded connection, timeout, DNS, or TLS transport failure.
- `http_status`: a non-specialized remote status outcome; retain sanitized status only.
- `unauthorized`: authentication/authorization failed; never retry blindly.
- `rate_limited`: documented or recognized quota response; bounded retry may follow headers.
- `not_found`: requested resource/path is absent.
- `no_data`: a valid request has no domain result.
- `unsupported_context`: valid source, but current client/game/product context cannot provide the request.
- `parse`: content cannot be parsed safely.
- `schema_drift`: required shape/semantic invariant changed.
- `policy_blocked`: use is forbidden or unreviewed.

## Compatibility matrix

For each primary/fallback pair, compare source identity, population, scope, patch/version, locale, region/platform, queue/lane/tier, timestamp/freshness, methodology, units, permission, and attribution. Mark only `compatible`, `compatible_with_label`, or `blocked`. A fallback cannot silently erase provenance or change a user-visible claim.

## Change control

A schema, endpoint, policy, provider-methodology, or cache change requires contract review, fixture update, drift test, and either migration or explicit version increment. Delete obsolete aliases after callers migrate; do not preserve ambiguous behavior with an undocumented shim.
