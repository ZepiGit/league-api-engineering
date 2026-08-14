# Optional case study: LoLCompanion

**Status:** optional illustrative case study. This file is not a required dependency, installation path, or assumption of the public skill. A product may omit it entirely and still use every public workflow.

## Scenario

A Windows desktop League companion may combine several source classes while keeping their claims separate:

| Feature need | Candidate source class | Correct boundary |
|---|---|---|
| Local pre-game/client UI context | LCU | Local, ephemeral, observed-undocumented integration with no credential persistence |
| Local active-game display | Live Client Data | Local game-session state only; no remote observation or hidden-state inference |
| Champion/item names and assets | Data Dragon | Pinned patch/version and locale-aware static data |
| Remote match/ranked information | Riot Web APIs | Server-side or otherwise controlled key custody, documented routing and quotas |
| Optional aggregate build/trend views | Third-party provider | Terms/attribution/population/compatibility gate before display |

## What the specialization should add

A repository-local specialization can map these generic contracts to actual modules, symbols, provider configuration, user-visible labels, storage boundaries, and test commands. It should validate those claims against the repository at review time rather than copying them into this public package.

The specialization owns:

- current application architecture and source-code evidence;
- actual LCU/Live Client lifecycle handling and loopback transport implementation;
- Rust/Tauri or other stack conventions;
- provider mappings and product copy;
- local test and release commands;
- repository-specific security, accessibility, and regression gates.

## Example decision outcomes

- **Permitted with constraints:** show a pinned static item description from Data Dragon with version provenance and cache age.
- **Permitted with constraints:** show a local active-game field that the documented/evidenced service exposes, while the game is active, with session-only retention.
- **Blocked:** ship a Riot production key in the desktop app so it can query remote match data directly.
- **Blocked:** replace unavailable local live state with inferred enemy information or a remote aggregate labelled as live.
- **Compatible with label:** offer a reviewed third-party aggregate when the UI identifies its provider, population, patch, and freshness rather than calling it Riot/player-specific data.

## Transferable lesson

Separate source authority from product usefulness. A local endpoint may be useful but unstable; a documented remote source may be authoritative but unauthorized for a client architecture; a third-party source may be useful but semantically incompatible with the requested claim. The adapter contract, policy gate, provenance envelope, and test/canary evidence make those distinctions reviewable.
