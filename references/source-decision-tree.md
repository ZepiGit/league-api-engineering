# Source decision tree

**Review date:** 2026-08-13. This is a decision aid, not a claim that any endpoint is currently available. Recheck authoritative documentation and applicable terms at implementation time.

## Classify the data before choosing a source

| Need | First candidate | Authority | Stability | Do not use it for |
|---|---|---|---|---|
| Local client/session context | LCU | Riot client behavior; not a public product API | `observed-undocumented` unless current Riot documentation says otherwise | Remote users, hidden state, persistent data collection |
| Active in-game state for the local player | Live Client Data | Riot game-exposed local service | Operational behavior can vary by client/game state | Other players' hidden state or remote observation |
| Static, versioned game assets | Data Dragon | Riot-published static content | High when pinned by version; content changes per patch | Live state or account history |
| Remote account, match, ranked data | Riot Web APIs | Official developer platform | High within documented lifecycle, routing, and quota constraints | Keyless production access or cross-product redistribution without review |
| Game files, asset details, community-maintained metadata | CommunityDragon | Community project, not Riot product authority | Patch-dependent; schemas and availability may change | Official claims, entitlement decisions, or unsupported runtime behavior |
| Aggregate builds, trends, or analytics | Reviewed third-party provider | Provider-specific | Provider-specific; population and terms determine meaning | Silent substitution for Riot/player-specific data |
| Hidden, inferred, or prohibited state | None | None | N/A | Any implementation; return `unsupported_context` or `policy_blocked` |

## Decision sequence

1. **State the user-visible claim.** Name the player population, region, patch/version, queue, locale, freshness, and output semantics.
2. **Choose the narrowest authoritative source.** Prefer an official documented source for its documented domain. A locally reachable service does not become a remote API.
3. **Check access feasibility.** Record authentication type, key custody, regional/platform routing, rate limits, network topology, and whether the product can legitimately obtain access. Never solve missing authorization by embedding a key or collecting another user's credentials.
4. **Check policy and product fit.** Review Riot and provider terms, attribution, redistribution, privacy, local-only constraints, and anti-cheat safety. Use [`policy-and-product-gates.md`](policy-and-product-gates.md).
5. **Check semantic fit.** Compare source population, sampling method, patch, queue, tier, lane, region, locale, latency, and no-data meaning to the requested claim.
6. **Design the failure path first.** Map expected failures to the required taxonomy; define what remains useful offline, what is stale, and what must be hidden rather than guessed.
7. **Create an adapter contract.** Include provenance and a dated evidence record before implementation. See [`adapter-contract.md`](adapter-contract.md).
8. **Validate with sanitized fixtures and a canary where legitimate.** Treat drift or a failed terms review as a release blocker, not an invitation to loosen validation.

## Hard rejections

Reject the candidate if any answer is yes:

- Does it require an embedded production credential, shared personal token, cookie, or LCU password?
- Does it require process manipulation, injection, memory reading, anti-cheat interference, packet interception, or hidden-state extraction?
- Would it report a materially different population or freshness as if it were the requested data?
- Are terms, attribution, redistribution, or compatibility unknown for the intended product use?
- Does it depend on a remote TLS bypass, blind retry of non-transient failures, or an undocumented behavior claimed as stable?

## Evidence record minimum

For every accepted source, record the source URL or reproducible observation, review date, evidence class, authority, stability expectation, policy/terms review date, route/version assumptions, and next revalidation trigger. `Verified-current` evidence expires when documentation, terms, route, patch, client version, or provider contract changes.
