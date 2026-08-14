# CommunityDragon

**Review date:** 2026-08-13. **Authority:** CommunityDragon is a community-maintained project and is not Riot's public product API authority. It can be valuable evidence for assets and game-file-derived metadata, but it does not establish Riot support, product permission, or a stable external contract. **Stability:** patch, repository, schema, and distribution behavior can change without a Riot compatibility guarantee.

## When it is appropriate

Use CommunityDragon only after the feature has passed product, licensing, attribution, redistribution, and maintenance review. It can be a candidate for supplemental static metadata or asset discovery where the product explicitly communicates provider provenance and tolerates drift.

Project entry point: <https://www.communitydragon.org/>. Availability alone is not evidence of redistribution permission or schema stability; record any retrieval failure as an evidence gap and recheck before implementation.

Do not use it to:

- claim official Riot support or canonical product behavior beyond the published artifact;
- bypass absent Riot access, client restrictions, or policy requirements;
- obtain hidden runtime state, entitlement data, or player-private information;
- substitute an unreviewed community population for official/player-specific data;
- rely on an observed file layout as a permanent API.

## Contract requirements

An adapter using CommunityDragon must explicitly record:

- exact artifact/repository URL, revision or patch marker, and retrieval date;
- `observed-undocumented` or other honest evidence class—not `verified-current` merely because a file exists;
- source owner, attribution text, license/terms review date, and redistribution decision;
- intended data domain, source population, locale/version dimensions, and user-facing provenance;
- schema fingerprint, drift action, cache key/TTL, and allowed stale window;
- compatibility analysis for every fallback.

If any of these cannot be established, return `policy_blocked` or choose another source.

## Patch and schema drift

Treat every patch as a potential contract change. Pin a revision or version marker, parse defensively, preserve unknown fields separately only when safe, and reject changed required fields as `schema_drift`. Do not silently remap renamed concepts, mix records across versions, or use a previous patch as if it were current.

A drift fingerprint should be based on sanitized field structure and selected semantic invariants, not a raw bulk payload or personally identifying content. Review changes before re-enabling an affected feature.

## Caching and fallback

Cache keys must include source identity, artifact/revision, patch/version, locale, and normalization version. A CommunityDragon response is not automatically compatible with Data Dragon or a third-party source just because names appear similar. Compare fields, timing, scope, license, and user-visible claim first; if different, label it as a distinct source.

## Testing and review

Use small, sanitized fixture fragments pinned to a known review marker. Test missing asset, removed field, renamed field, malformed data, version mismatch, unavailable source, and policy-blocked redistribution. A canary can verify an approved artifact's availability and fingerprint; it cannot prove long-term stability or broaden permissions. See [`testing-and-canaries.md`](testing-and-canaries.md).
