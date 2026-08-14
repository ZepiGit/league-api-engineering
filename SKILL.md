---
name: league-api-engineering
description: Use when implementing, auditing, debugging, researching, or governing League of Legends data integrations across Riot, local-client, static-data, and third-party sources.
license: MIT
metadata:
  version: "2.0.0"
---

# League API Engineering

Select exactly one primary mode. For a mixed request, state the dominant mode and the secondary deliverable before proceeding.

| Mode | Use for | Required result |
|---|---|---|
| `implement` | Adding or changing a data integration | Source decision → adapter contract → sanitized fixtures/tests → implementation plan or code → gates |
| `audit` | Assessing an existing integration | Inventory → evidence labels → risk matrix → prioritized, source-specific fixes |
| `debug` | A failing or misleading integration | Reproduction → failure class → transport/schema/cache/fallback inspection → fix proof |
| `research` | Choosing a source or checking current facts | Dated evidence map → source assessment → decision |
| `policy` | Whether data use or product behavior is allowed | Product/data review → policy gate → permitted, constrained, or blocked decision |

## Non-negotiable gates

Reject a design rather than work around a failed gate:

- **Secrets and privacy:** never embed, persist, or log Riot keys, LCU credentials, bearer tokens, cookies, PII, or real player histories.
- **Local-client safety:** no injection, hooks, process-memory access, memory scanning, anti-cheat bypass, hidden-state extraction, or claims of exclusive-fullscreen control. Loopback certificate relaxation is limited to a client explicitly bound to `127.0.0.1` or `localhost`; it is never reusable for remote HTTPS.
- **Authority and terms:** do not represent an undocumented endpoint or provider as officially supported. Verify applicable terms, attribution, redistribution, authentication, and rate-limit conditions before use.
- **Fallback truthfulness:** a fallback must preserve population, scope, freshness, patch, locale, queue, and provenance semantics. Materially different data is a separate result, not a silent substitute.
- **Unsupported requests:** do not invent MMR/ELO estimates, infer hidden state, or expose unavailable player information. Return `policy_blocked` or `unsupported_context` with the constraint.

## Source-decision workflow

1. Classify the requested data: local session, active match, static/versioned data, remote account/match/ranked data, aggregate trend data, or unsupported/hidden state.
2. Start with [`source-decision-tree.md`](references/source-decision-tree.md); choose candidates by authority, access, routing, freshness, stability, patch coverage, latency, terms, privacy, attribution, rate limits, and failure behavior.
3. Apply hard gates before scoring. A source needing an embedded production key, unsafe local access, prohibited data, unreviewed redistribution, or an incompatible fallback is rejected.
4. Record an evidence class for each material claim:
   - `verified-current`: directly supported by a dated authoritative source or current reproducible observation;
   - `observed-undocumented`: reproduced behavior not guaranteed by an authority;
   - `historical`: formerly documented or observed, not safe to assume current;
   - `inference`: a reasoned conclusion that needs validation before production.
5. Write or update an adapter contract using [`adapter-contract.md`](references/adapter-contract.md), then adopt cache/fallback, testing, and canary controls.

## Failure vocabulary

Use one primary error class and retain raw sanitized diagnostics separately: `offline`, `unauthorized`, `rate_limited`, `not_found`, `no_data`, `unsupported_context`, `transport`, `http_status`, `parse`, `schema_drift`, or `policy_blocked`.

Never blindly retry `unauthorized`, `policy_blocked`, `parse`, or `schema_drift`. See [`caching-and-fallbacks.md`](references/caching-and-fallbacks.md).

## Audit output contract

An audit emits a dated artifact with:

1. scope, data classes, and adapter inventory;
2. source/endpoint map with authority, stability, evidence class, and terms-review date;
3. credential, privacy, local-access, routing, versioning, and attribution findings;
4. cache, no-data, retry, drift, and fallback compatibility findings;
5. a risk matrix: severity, likelihood, affected behavior, evidence, and concrete remediation;
6. prioritized fixes, blocked items, and verification criteria.

Do not label an assumption as verified. Do not call a source safe merely because it works once.

## Progressive disclosure

- Official and local source choices: [`riot-web-apis.md`](references/riot-web-apis.md), [`lcu.md`](references/lcu.md), [`live-client-data.md`](references/live-client-data.md), [`data-dragon.md`](references/data-dragon.md), [`communitydragon.md`](references/communitydragon.md).
- External sources and product policy: [`third-party-providers.md`](references/third-party-providers.md), [`policy-and-product-gates.md`](references/policy-and-product-gates.md).
- Engineering controls: [`adapter-contract.md`](references/adapter-contract.md), [`caching-and-fallbacks.md`](references/caching-and-fallbacks.md), [`testing-and-canaries.md`](references/testing-and-canaries.md).
- Optional bounded example: [`case-study-lolcompanion.md`](references/case-study-lolcompanion.md).

Run `python scripts/validate.py .` from the package root before publishing when the validator is present.
