# League Client Update (LCU)

**Review date:** 2026-08-13. **Authority:** Riot is authoritative only where it publishes an applicable client or developer contract. Common LCU endpoint knowledge is frequently community-observed rather than a public, stable Riot API contract. **Stability:** treat endpoint paths, payloads, authentication details, certificates, ports, and availability as `observed-undocumented` unless supported by current Riot documentation.

## Permitted engineering boundary

LCU is a local, user-owned-client integration surface. Use it only for the currently running local client after the product has a legitimate local-use reason and policy review. It is not a remote service, multi-user backend source, or reason to collect client credentials.

Current source entry points:

- Riot League Client guidance: <https://developer.riotgames.com/docs/lol#league-client-api>
- Community-observed lockfile and local authentication notes: <https://hextechdocs.dev/getting-started-with-the-lcu-api/>
- Community-observed WebSocket notes: <https://hextechdocs.dev/getting-started-with-the-lcu-websocket/>

The community references describe observed behavior; they do not upgrade it to a supported Riot Web API.

An LCU adapter must state:

- local-only scope and supported operating context;
- discovery method and minimum client-state requirements;
- endpoint family and evidence class for each path;
- authentication handling without persistence or logging;
- loopback-only TLS handling, if justified;
- version/schema observation and drift response;
- no-client, client-closed, unsupported-flow, and policy-blocked behavior.

## Security rules

- Never persist, expose, or log the local authentication password, lockfile contents, authorization header, cookies, process arguments, or full client payloads.
- Never use injection, hooks, DLL loading, memory reading, process-memory scanning, packet interception, anti-cheat interference, or hidden-state extraction.
- Never scan arbitrary processes or use elevated access merely to find an integration target.
- Scope any certificate exception to a client intentionally connecting to `127.0.0.1` or `localhost` for the local LCU transport. Do not set global TLS-disable flags, trust the certificate globally, proxy it remotely, or reuse the exception for external HTTPS.
- Do not claim an undocumented endpoint is stable or supported. Surface `schema_drift`, `unsupported_context`, or `policy_blocked` when appropriate.

## Discovery and lifecycle

Treat client presence as optional and transient. A correct adapter can start with no local client, observe the client closing or restarting, recover from port/credential rotation without retaining old secrets, and fail safely when an expected endpoint disappears.

Use narrow, documented-or-evidenced discovery; validate ownership and loopback address before connecting. Keep discovery data in memory only for the minimum connection lifetime. Do not convert it into a background surveillance mechanism.

## Failure behavior

| Situation | Class | Product behavior |
|---|---|---|
| Client not running or no supported local session | `unsupported_context` | Offer no local result; do not synthesize remote state |
| Loopback service cannot be reached | `offline` or `transport` | Retry only with a bounded lifecycle-aware policy |
| Local authentication fails | `unauthorized` | Discard ephemeral credentials; do not retry or log them |
| Endpoint is absent in the current flow | `not_found` or `unsupported_context` | Record observed version and degrade explicitly |
| Payload is incompatible | `schema_drift` or `parse` | Quarantine the response and require review |

## Evidence and testing

Use sanitized recorded shapes or generated fixtures—not a user lockfile, session payload, account, or match history. A canary may confirm only allowed local conditions in a test environment and must redact all client identifiers and secrets. Recheck observed behavior after client patches. See [`testing-and-canaries.md`](testing-and-canaries.md).
