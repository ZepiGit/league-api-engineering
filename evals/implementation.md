# Implementation evaluation suite

Machine-readable cases: `implementation.json`.

| Case | Required implementation posture |
| --- | --- |
| `implementation.lcu-champ-select-adapter` | Typed errors, in-memory local authentication, isolated loopback TLS, bounded retry, sanitized fixtures, opt-in canary. |
| `implementation.third-party-build-stats` | Terms and attribution gates, population-preserving normalization, complete cache keys, explicit compatible fallback matrix. |
| `implementation.compatible-static-fallback` | Verify exact static-data compatibility before fallback; expose actual provenance; reject an unsatisfied contract. |

A proposal passes only if all boolean criteria are met. Implementation details may vary by language, but remote TLS verification, secret boundaries, provenance, cache identity, failure semantics, and policy gates cannot be weakened.
