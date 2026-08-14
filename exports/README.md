# Export guidance

This directory's contents are the published package root: the public repository (`https://github.com/ZepiGit/league-api-engineering`) is this directory, flattened, with no wrapper folder. Do not include local caches, credentials, real match data, repository-only specializations, or user-specific paths.

Before creating a distribution archive, run from the package root:

```sh
python scripts/validate.py .
```

A distribution archive built from this directory nests every file under a `league-api-engineering/` top-level folder and includes its manifests, references, schemas, templates, examples, scripts, evals, and license — that is the shape produced by extracting a release ZIP or by `git clone` followed by `cd league-api-engineering`. Consumers install the extracted or cloned package as `league-api-engineering` under their local Claude-compatible skills directory.
