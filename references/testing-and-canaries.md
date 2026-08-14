# Testing and canaries

Tests prove the adapter contract under deterministic conditions. Canaries provide narrow current evidence after policy review. Neither substitutes for source/terms review, and a successful canary does not prove long-term availability or permission.

## Fixture rules

Fixtures are sanitized, minimal, deterministic contract artifacts:

- use generated identifiers and representative non-secret values;
- exclude Riot keys, bearer tokens, LCU passwords, cookies, real account identifiers, real match histories, raw lockfiles, and private URLs;
- include source class, schema ID, version/patch, locale/routing dimensions, provenance, and expected error/result classification;
- include valid and intentionally invalid cases so validators prove rejection behavior;
- preserve only the fields needed to defend a contract invariant;
- version fixtures alongside adapter-contract and normalized-schema changes.

A fixture demonstrates a known shape. It is not proof that an endpoint remains supported or that a provider’s terms allow production use.

## Minimum behavioral suite

For each adapter, test observable outcomes—not plumbing:

1. valid normalization with source provenance and version/context dimensions;
2. valid empty/no-data response distinct from not-found;
3. offline/transport timeout and cancellation behavior;
4. authorization and rate-limit behavior without secret exposure or blind retry;
5. route/region/platform and patch/locale mapping boundaries;
6. cache hit, expiry, stale labeling, and invalidation;
7. fallback compatibility, `compatible_with_label`, and blocked substitution;
8. parse failure and required-field/schema drift quarantine;
9. policy-blocked/unsupported-context behavior;
10. redaction of logs, audit artifacts, and diagnostics.

For local data, include no client/game, service starting, active valid state, ending session, and restart/credential rotation without secret persistence. For static data, include pinned-version and version-mismatch paths. For third parties, include changed methodology/population and terms-expiry blocks.

## Drift detection

Define a stable fingerprint of required field structure and selected semantic invariants. Compare normalized shape, required fields, types, enum/mapping assumptions, and expected source metadata. Do not fingerprint whole raw payloads if that would retain unnecessary data.

On drift:

1. return `schema_drift` for the affected adapter result;
2. stop unsafe normalization and incompatible fallback;
3. retain only a separately permitted stale result with honest labeling;
4. capture sanitized structural evidence and alert the owner;
5. review terms, source documentation, mapping, contract, fixtures, and migration before re-enabling.

## Canary design

A canary is optional and must be legitimate, low-impact, bounded, and non-destructive.

- Confirm the endpoint/source and access are authorized for automated checking.
- Use least-privileged non-user or approved test context where supported; do not create a canary by storing a production key in a repository or a desktop client.
- Bound timeout, retry, request volume, data retention, and log content.
- Check a compact success/status signal plus an approved schema fingerprint—not full player/match payloads.
- Record timestamp, source/version, route, result class, and redacted diagnostic only.
- Fail closed on authorization, policy, parse, or drift issues; do not make an alternate provider silently mask a failing canary.

## Audit-ready evidence

A verification record includes contract/fixture version, command or scenario, environment class, result, error class if any, sanitized fingerprint, review date, and remediation link. Avoid absolute user paths, credentials, raw responses, and personal data.

Run the package validation command from the package root before publication when available:

```sh
python scripts/validate.py .
```
