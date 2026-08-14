# Riot Web APIs

**Review date:** 2026-08-13. **Authority:** Riot Games Developer Platform documentation and applicable developer policies are authoritative for documented endpoints, products, authentication, routing, quotas, and permitted use. **Stability:** documented behavior remains subject to Riot lifecycle, policy, version, and operational changes; validate current documentation before release.

## Use when

Use Riot Web APIs for documented remote account, match, ranked, mastery, league, spectator, status, or related data that a product is authorized to request. They are not a substitute for local client state, active-match local telemetry, static assets, or aggregate analytics.

Start at the current Riot Developer Portal and document, per adapter:

- endpoint family and exact documented purpose;
- platform and regional routing domains; do not infer one from the other;
- authentication model, development/production key class, custody owner, and rotation path;
- rate-limit scope and headers, retry conditions, and backoff bounds;
- identifiers, retention, privacy, and redistribution constraints;
- patch/version and locale implications; and
- a dated documentation/policy review URL.

Current authoritative entry points:

- API catalog: <https://developer.riotgames.com/apis>
- League developer policy and product guidance: <https://developer.riotgames.com/docs/lol>
- General policies: <https://developer.riotgames.com/policies/general>
- API terms: <https://developer.riotgames.com/terms>

## Authority is not availability

A Riot endpoint can be authoritative for its domain while unavailable to a particular product because of missing approval, incorrect routing, quota exhaustion, disabled access, unavailable account data, or policy restrictions. Return the correct failure class rather than replacing it with another source:

| Condition | Primary class | Correct behavior |
|---|---|---|
| No network or resolver/connectivity failure | `offline` or `transport` | Preserve cached data only under its stated stale policy |
| Missing/invalid/expired authorization | `unauthorized` | Do not retry blindly or fall back to credentials held by clients |
| Quota response | `rate_limited` | Honor documented headers and bounded retry rules |
| Resource does not exist | `not_found` | Distinguish from a valid empty response |
| Valid query has no domain data | `no_data` | Preserve the source’s no-data semantics |
| Unsupported product/data request | `unsupported_context` or `policy_blocked` | Explain the constraint without inventing a result |

## Key custody

- Keep server-side production keys in a suitable secret store or equivalent controlled runtime configuration; never ship them in a desktop, web, mobile, CLI, fixture, log, or skill artifact.
- Use least privilege and distinct environments. Rotation must not require a client release.
- Redact authorization headers, query keys, account identifiers, and raw error bodies in logs and audit artifacts.
- A public client cannot safely protect a shared production key. If a design needs one, change the architecture or block it.

## Routing and identity

Model platform routing and regional routing as explicit adapter inputs. Do not derive them from UI labels, locale, or an unverified country mapping. Normalize identifiers only when the documented endpoint permits the transformation, retain the source identity type, and avoid logging personal identifiers.

## Rate limits and retries

Respect documented response headers and quota semantics. Retry only bounded transient conditions such as selected `transport`, `http_status`, or `rate_limited` outcomes. Never retry `unauthorized`, `not_found`, `no_data`, `parse`, `schema_drift`, `unsupported_context`, or `policy_blocked` as if they were network failures.

## Verification

Use sanitized fixtures for normal, no-data, quota, authorization, routing, and schema-change paths. If a legitimate canary exists, use a controlled non-user account or endpoint permitted by Riot policy; record only a fingerprint and sanitized status, never live identities or payloads. See [`testing-and-canaries.md`](testing-and-canaries.md).
