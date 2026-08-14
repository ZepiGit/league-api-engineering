# Third-party providers

**Review date:** 2026-08-13. **Authority:** a third-party provider is authoritative only for the data and methodology it explicitly publishes under its own contract. It is not Riot authority and must not be represented as such. **Stability:** endpoint availability, schemas, source populations, rates, attribution, licenses, and product terms are provider-specific and may change without Riot notice.

## Admission gate

A provider is eligible only after all checks below have a dated, reviewable answer:

1. **Terms and permission:** documented authorization for the intended access method, product use, storage, redistribution, commercial use if applicable, and automated access.
2. **Attribution:** required attribution text, placement, link, brand use, and removal/expiry behavior are known and implementable.
3. **Data meaning:** population, sampling, regional scope, patch coverage, queue/lane/tier definitions, ranking methodology, locale, refresh cadence, and no-data semantics match the feature claim.
4. **Authentication and custody:** API keys/tokens have a legitimate server-side custody model. No shared secret can be shipped to an untrusted client.
5. **Schema and operational risk:** versioning, rate limits, error model, retention, deletion, availability, and schema-drift response are defined.
6. **Fallback compatibility:** every fallback preserves the relevant user-visible claim or is presented as a distinct source.

If a check is absent, ambiguous, expired, or incompatible, return `policy_blocked`; do not scrape, infer permission from accessibility, or quietly switch sources.

## Population is product semantics

“Build data,” “win rate,” “rank,” and “meta” are not interchangeable facts. Provider populations may differ by sample size, data collection, rank band, region, patch, queue, role taxonomy, filtering, and update time. The adapter must retain these dimensions in provenance and make material distinctions visible to consumers.

Never replace a requested source with a provider that has a different population while retaining the original label. For example, a global aggregate cannot silently stand in for a regional, tier-filtered, current-patch result.

## Adapter requirements

For each provider, record:

- legal/terms and attribution URLs with review date;
- source identifier, endpoint family, auth method, route/region rules, and rate-limit policy;
- methodology/population statement, patch freshness, locale, and category mappings;
- normalized output schema with original source/provenance fields;
- `no_data`, unavailable, quota, authorization, parse, and drift behavior;
- cache key/TTL/stale rules and compatible fallback matrix;
- fixture provenance and a sanitized drift fingerprint.

See [`adapter-contract.md`](adapter-contract.md) for the full contract.

## Failure behavior

| Event | Class | Required response |
|---|---|---|
| Terms or attribution unreviewed | `policy_blocked` | Do not access, display, cache, or redistribute |
| Credentials invalid/missing | `unauthorized` | Do not retry blindly or move credentials client-side |
| Provider quota reached | `rate_limited` | Follow documented headers and bounded backoff |
| No matching population/data | `no_data` | Preserve provider-specific no-data semantics |
| Endpoint/content moved | `not_found` or `http_status` | Do not scrape a replacement without a new gate |
| Shape/methodology changed | `schema_drift` | Stop affected normalization pending review |

## Review cadence

Revalidate provider terms, attribution, schema fingerprint, methodology, and fallback compatibility before launch; after an API/terms/patch/model change; and on any drift or user-facing discrepancy. A successful request is evidence of temporary reachability, not permanent permission or equivalence.
