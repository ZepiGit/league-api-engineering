# Debugging evaluation suite

Machine-readable cases: `debugging.json`.

| Case | Required diagnosis |
| --- | --- |
| `debugging.live-client-offline` | Local active-match endpoint absence is normal outside its context; back off transient checks; retain typed parse and drift diagnostics. |
| `debugging.data-dragon-schema-drift` | A required-field change is schema drift, not retryable transport noise; stale cache must remain version-labeled and policy-limited. |
| `debugging.third-party-population-mismatch` | Materially different build-stat populations are incompatible; do not silently substitute or erase provenance. |

Judge root-cause classification before proposed fixes. Passing responses distinguish transport, authorization, parse, drift, policy, and no-data outcomes rather than suppressing errors or masking them with a generic fallback.
