# Policy evaluation suite

Machine-readable cases: `policy.json`.

| Case | Required decision |
| --- | --- |
| `policy.remote-history-local-only` | Reject a local-only remote-account-data design that would require an embedded production Riot key. |
| `policy.third-party-build-provider` | Fail closed without verified terms, redistribution rights, attribution, drift, and compatible fallback gates. |
| `policy.compatible-fallback-decision` | Permit fallback only when source rights, semantics, version, locale, freshness, and provenance are demonstrably compatible. |

Each response must state a permitted or blocked result, not merely identify risks. A policy pass cannot be achieved by suggesting credentials, scraping, attribution, or a fallback as a later informal concern.
