# Data Dragon

**Review date:** 2026-08-13. **Authority:** Data Dragon is Riot-published static game-data distribution and is authoritative for the static assets and fields it publishes for a specified version/locale. **Stability:** versioned artifacts are comparatively stable once fetched, but content, schemas, locales, and release timing change across patches. Pin versions and validate shape before using new releases.

## Use it for static, versioned data

Use Data Dragon for items such as champions, spells, items, runes, images, maps, and localized static metadata when those assets are published in the selected version. Do not use it as evidence of active game state, player account state, matchmaking state, live balance behavior outside its published data, or community trend data.

Authoritative League guidance and the public version index:

- <https://developer.riotgames.com/docs/lol#data-dragon>
- <https://ddragon.leagueoflegends.com/api/versions.json>

## Versioning discipline

Every request and cache key must include the intended game-data version and locale when applicable. A UI label such as “latest” is not a stable contract:

- resolve the target version through the current published version source;
- persist the resolved version with normalized data and provenance;
- prevent a new patch fetch from silently overwriting a pinned result;
- invalidate or rebuild derived indexes deliberately when version changes;
- label stale data with its actual version rather than relabeling it as current.

Treat availability lag between a game patch and static-data publication as `no_data`, `not_found`, or `unsupported_context` according to the documented response—not as permission to mix versions.

## Locale and identity

Make locale explicit. Locale affects display text and may affect client-visible naming but must not be used as a substitute for platform/region routing. Preserve stable identifiers separately from localized labels. If a field is missing for a locale, distinguish that from an absent object or a failed parse.

## Asset integrity and provenance

Record source URL family, resolved version, locale, retrieval time, integrity/fingerprint where available, and evidence class. Cache raw and normalized artifacts only within their documented license/policy and product-use constraints. Do not redistribute bulk assets or derive a broader license merely from public accessibility; review current Riot terms for the intended distribution.

## Failure behavior

| Condition | Class | Required behavior |
|---|---|---|
| Network unavailable | `offline` or `transport` | Use a version-labeled cache only within stale policy |
| Requested version/object absent | `not_found` | Do not silently use a different version |
| Published index lacks a needed asset | `no_data` or `unsupported_context` | Surface the source limitation |
| New payload shape | `schema_drift` | Block affected normalization pending review |
| Invalid content | `parse` | Keep prior validated data only when explicitly allowed |
| Redistribution/use not reviewed | `policy_blocked` | Block export or product feature |

## Testing

Fixtures must cover two versions, at least one locale difference, missing asset, changed field, and offline cache behavior. A canary should fetch only approved public metadata, validate a compact fingerprint and schema expectation, and never establish that “latest” is safe without version review. See [`caching-and-fallbacks.md`](caching-and-fallbacks.md) and [`testing-and-canaries.md`](testing-and-canaries.md).
