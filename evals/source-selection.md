# Source-selection evaluation suite

Machine-readable cases: `source-selection.json`.

| Case | Required decision |
| --- | --- |
| `source-selection.lcu-champ-select` | Choose the local League Client API; retain lockfile credentials only in memory; scope certificate relaxation to loopback. |
| `source-selection.live-client-active-match` | Choose Live Client Data for active match state; treat absence outside a game as normal; preserve a Vanguard-safe boundary. |
| `source-selection.riot-web-routing-backend` | Separate platform and regional routing; require a trusted backend for production Riot credentials; block local-only remote account access. |
| `source-selection.data-dragon-versioning` | Use versioned static data; key and label records by patch and locale; detect schema drift from sanitized fixtures. |

Evaluate every criterion as a binary pass/fail proposition. The expected evidence and error classes are required output labels, not suggestions. A response must not replace a source merely because it is easier to access when authority, freshness, population, terms, privacy, or routing constraints differ.
