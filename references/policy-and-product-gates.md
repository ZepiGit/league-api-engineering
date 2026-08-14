# Policy and product gates

**Review date:** 2026-08-13. This reference describes engineering gates, not legal advice. **Authority:** current Riot policies, developer terms, product-specific agreements, and applicable law control their respective obligations. **Stability:** terms, permissions, and product requirements can change; dated review is required before release and after a material change.

## Gate order

Evaluate policy before implementation and again before release. A feature is permitted only when every applicable gate has a documented owner, evidence URL or approved internal record, review date, and product behavior.

| Gate | Required question | Block when |
|---|---|---|
| Data scope | Is every requested field intentionally exposed by the chosen source? | It needs hidden, inferred, or unavailable state |
| Access | Can the product obtain access without shared client secrets or unsafe local techniques? | It needs embedded credentials, credential harvesting, injection, hooks, memory access, or anti-cheat interference |
| Terms | Do Riot/provider terms permit this access, storage, display, automation, attribution, and redistribution? | Permission is absent, ambiguous, expired, or cannot be implemented |
| Privacy | Is collection minimal, disclosed as needed, retained only as justified, and redacted from observability? | It stores/logs identifiers, credentials, cookies, personal histories, or unnecessary raw payloads |
| Truthfulness | Does the UI accurately state source, population, freshness, patch, and limitations? | It relabels stale/different data as current/equivalent or invents estimates |
| Safety | Is loopback isolation narrow and are remote transports verified normally? | TLS verification is globally disabled or a loopback exception can reach remote HTTPS |
| Operations | Are drift, revocation, no-data, outage, and rate-limit outcomes safe? | It retries irreversible errors, hides failures, or continues after drift |

## Mandatory blocked outcomes

Return `policy_blocked` or `unsupported_context`—not an invented workaround—when a request would:

- extract or infer hidden game/client state;
- inject code, hook APIs, inspect process memory, scan memory, bypass anti-cheat, intercept traffic, or manipulate game/client processes;
- embed/distribute Riot keys, bearer tokens, LCU credentials, cookies, or another user’s secret;
- disable remote TLS verification or reuse loopback certificate handling for external HTTPS;
- present an estimate as official MMR/ELO/rank or expose unavailable player data;
- scrape or use a third-party provider without explicit terms/attribution/redistribution review;
- silently replace data with a materially different population, patch, region, tier, queue, locale, or freshness.

## Decision artifact

For each product decision, record:

- feature and user-visible claim;
- data inventory and source/endpoint classes;
- authority/evidence class, terms URLs, review dates, and accountable owner;
- access/authentication model and data-flow boundary;
- privacy/retention/telemetry decision;
- attribution and provenance presentation;
- fallback compatibility decision;
- outcomes: `permitted`, `permitted_with_constraints`, or `blocked`;
- re-review triggers: policy update, new source, schema drift, patch/version change, provider methodology change, or product scope expansion.

## Product copy and behavior

A permitted feature still must be honest under failure. Label stale data, identify provider/source where material, distinguish `no_data` from an error, and remove or disable a feature when a gate expires. Do not make compliance claims based solely on a successful request.

## Review escalation

Escalate ambiguous terms, personal-data processing, commercial redistribution, account linkage, long-term retention, and data-deletion obligations to the appropriate product, privacy, legal, or platform authority. Engineering must fail closed until the decision is recorded.
