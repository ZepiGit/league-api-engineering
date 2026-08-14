<div align="center">
  
# ⚔️ League API Engineering

**Evidence-led, policy-safe engineering guidance for League of Legends data integrations.**

[![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)](#get-the-package)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Agent Skill](https://img.shields.io/badge/Agent_Skill-Claude_&_OMP-8A2BE2.svg)](#install-in-claude-code-or-omp)

</div>

<br>

> *"Stop guessing your data architecture. Start engineering it."*

`league-api-engineering` is a product-neutral **Agent Skills package** built to help AI coders and developers design, audit, debug, research, and govern production integrations with League of Legends data sources.

It acts as an engineering companion that helps an agent choose an appropriate source, record evidence and policy decisions, design explicit adapter boundaries, preserve source provenance, and reject unsafe or incompatible approaches. 

*(Note: It is not an API client, Riot endorsement, or authorization to access restricted data.)*

---

## 🎯 What it covers

- 🔌 **Source Selection:** Riot Web APIs, Data Dragon, LCU, Live Client Data, and CommunityDragon.
- ⚖️ **Provider Governance:** Third-party provider due diligence and compatible fallback decisions.
- 🛡️ **Compliance & Policy:** Source authority, stability, terms, privacy, and attribution distinctions.
- 🏗️ **Architecture:** Adapter, cache, error, fixture, drift, and canary contracts.
- 🛑 **Guardrails:** Explicit outcomes for inaccessible, unsupported, or policy-blocked requests.

💡 **Usage:** Read [`SKILL.md`](SKILL.md) for routing, then follow its reference links for the selected mode.

---

## 🚀 Quick Start

Choose one:

- **Clone (recommended):**
  ```sh
  git clone https://github.com/ZepiGit/league-api-engineering.git
  cd league-api-engineering
  ```
  The clone's working directory *is* the package root — use `.` as the source in the commands below.

- **Release archive:** download `league-api-engineering-<version>.zip` from https://github.com/ZepiGit/league-api-engineering/releases, verify its checksum against the paired `.manifest.json`'s `archive_sha256` field, then extract it. Extraction produces a `league-api-engineering/` folder — use `./league-api-engineering` as the source in the commands below, run from the directory you extracted into.

## 🛠️ Install in Claude Code or OMP
### Claude Code

Copy the package into the local skills directory. Replace `SOURCE` with `.` (clone) or `./league-api-engineering` (release archive), per the acquisition method above:

```powershell
Copy-Item -Recurse -Force SOURCE "$HOME\.claude\skills\league-api-engineering"
```

On POSIX shells:

```sh
mkdir -p ~/.claude/skills
cp -R SOURCE ~/.claude/skills/league-api-engineering
```

Restart or reload the host after installation if it does not discover new skills automatically.

### Oh My Pi (OMP)

OMP discovers Claude-compatible local skills from the same `~/.claude/skills/` location. Copy the package there using the platform-appropriate command above, then invoke it by its skill name: `league-api-engineering`.


## ✅ Validate

From the package root, run:

```sh
python scripts/validate.py .
```

For a standalone source assessment, adapter contract, or fixture, use each script's `--help` for its accepted path and invocation. The public validator is designed to fail closed: resolve validation findings before publishing or installing.

## 📦 Package boundaries

This package has no required dependency on a particular League application or repository. The optional [`case-study-lolcompanion.md`](references/case-study-lolcompanion.md) is a bounded example, not an installation requirement.

## 📄 License

MIT; see [`LICENSE`](LICENSE).
