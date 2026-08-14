# League API Engineering

`league-api-engineering` is a product-neutral Agent Skills package for designing, auditing, debugging, researching, and governing production integrations with League of Legends data sources.

Version: **2.0.0**

It helps an agent choose an appropriate source, record evidence and policy decisions, design explicit adapter boundaries, preserve source provenance, and reject unsafe or incompatible approaches. It is not an API client, Riot endorsement, or authorization to access restricted data.

## What it covers

- Riot Web APIs, Data Dragon, LCU, Live Client Data, and CommunityDragon;
- third-party provider due diligence and compatible fallback decisions;
- source authority, stability, terms, privacy, and attribution distinctions;
- adapter, cache, error, fixture, drift, and canary contracts;
- explicit outcomes for inaccessible, unsupported, or policy-blocked requests.

Read [`SKILL.md`](SKILL.md) for routing, then follow its reference links for the selected mode.

## Get the package

Choose one:

- **Clone (recommended):**
  ```sh
  git clone https://github.com/ZepiGit/league-api-engineering.git
  cd league-api-engineering
  ```
  The clone's working directory *is* the package root — use `.` as the source in the commands below.

- **Release archive:** download `league-api-engineering-<version>.zip` from https://github.com/ZepiGit/league-api-engineering/releases, verify its checksum against the paired `.manifest.json`'s `archive_sha256` field, then extract it. Extraction produces a `league-api-engineering/` folder — use `./league-api-engineering` as the source in the commands below, run from the directory you extracted into.

## Install in Claude Code or OMP

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

## Validate

From the package root, run:

```sh
python scripts/validate.py .
```

For a standalone source assessment, adapter contract, or fixture, use each script's `--help` for its accepted path and invocation. The public validator is designed to fail closed: resolve validation findings before publishing or installing.

## Package boundaries

This package has no required dependency on a particular League application or repository. The optional [`case-study-lolcompanion.md`](references/case-study-lolcompanion.md) is a bounded example, not an installation requirement.

## License

MIT; see [`LICENSE`](LICENSE).
