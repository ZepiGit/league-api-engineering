# Contributor Guide

Keep this package product-neutral, evidence-led, and safe to publish.

- Treat `SKILL.md` as a router; put durable detail in focused references.
- Date claims about APIs, terms, and operational behavior. Distinguish `verified-current`, `observed-undocumented`, `historical`, and `inference`.
- Do not add credentials, tokens, cookies, real player data, user paths, or private repository assumptions.
- Reject unsafe local-client access, remote TLS bypasses, process inspection, injection, anti-cheat bypasses, memory access, and hidden-state extraction.
- Treat Riot documentation and applicable terms as the authority for official interfaces. Treat local endpoints and third-party interfaces as potentially unstable until evidenced and reviewed.
- Keep adapter contracts explicit about source population, routing, versioning, errors, cache/fallback behavior, provenance, and terms review.
- Use only the Python standard library in package scripts. Scripts must work on Windows and POSIX paths.
- Run `python scripts/validate.py .` from this directory before packaging when the validator is present. Fix content defects; do not weaken gates.
