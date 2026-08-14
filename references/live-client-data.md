# Live Client Data API

**Review date:** 2026-08-13. **Authority:** Riot is the authority for any current documentation describing game-exposed local data. **Stability:** availability and response fields are tied to client/game state and can change with patches; use current Riot documentation where available and classify unverified behavior as `observed-undocumented`.

## Scope

Live Client Data is appropriate for local, in-progress game context exposed by the running game. It is not an authorization to observe another player remotely, derive hidden state, record user histories without a policy basis, or predict unavailable information.

Current Riot League guidance is the source of authority: <https://developer.riotgames.com/docs/lol#game-client-api>. Treat a locally observed path or field that is absent there as `observed-undocumented`, not as a stable public contract.

Before use, define:

- who is running the product and whether the game is locally active;
- the intended user-visible feature and exact freshness requirement;
- exposed versus inferred fields;
- patch/client version assumptions;
- whether collection ends when the local game ends;
- retention, telemetry, and consent requirements for any derived data.

## Local transport safety

The service is commonly described as a local HTTPS interface. A narrowly scoped certificate relaxation may be necessary for a client intentionally connecting to its own loopback target, but it must be confined to that client and target (`127.0.0.1` or `localhost`). It must never disable TLS verification globally, apply to remote HTTPS, support a proxy, or leak into shared HTTP configuration.

Do not use process injection, hooks, memory reads, packet capture, anti-cheat bypasses, or unexposed game state to broaden the data model.

## State model

Treat the source as a state machine, not a permanently available endpoint:

1. no supported game session → `unsupported_context`;
2. game starts, but endpoint is not yet ready → bounded `transport`/`not_found` handling;
3. active game with valid exposed payload → normalize with timestamp, patch/version where available, and provenance;
4. game ends or service vanishes → stop polling, clear ephemeral session state according to retention policy, and do not represent stale state as live.

A poller needs bounded frequency, cancellation, timeout, and backoff. Never let a missing game create an unbounded retry loop.

## Normalization and absence

Record source time/receipt time, local-only provenance, known patch/version, and explicit field availability. Preserve distinctions among absent field, `null`, empty collection, no active game, and parse failure. Do not derive MMR/ELO, enemy hidden information, future events, or any fact the API does not expose.

## Failure handling

| Condition | Class | Required outcome |
|---|---|---|
| No game or unsupported mode | `unsupported_context` | State that live local data is unavailable |
| Loopback unreachable | `offline` or `transport` | Bounded lifecycle-aware retry only |
| Unsupported endpoint/feature | `not_found` | Do not replace with hidden-state extraction |
| Changed response shape | `schema_drift` | Quarantine/disable affected feature pending review |
| Malformed payload | `parse` | Keep prior result only if stale policy permits and label it stale |
| Exposed data conflicts with requested use | `policy_blocked` | Block the product behavior |

## Test evidence

Use generated/sanitized fixtures for pre-game, active-game, post-game, partial payload, malformed payload, and schema drift. A legitimate canary proves only that the allowed local flow works; it must not retain full game payloads or player histories. See [`testing-and-canaries.md`](testing-and-canaries.md).
