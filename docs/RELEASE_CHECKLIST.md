# Public release checklist

## Scientific consistency

- [ ] README, method mapping, configuration examples, and code describe the same workflow.
- [ ] Baseline thresholds and linking rules match the intended manuscript analysis.
- [ ] Output field definitions match the generated tables and manifest.
- [ ] Deterministic tie-breaking, gap handling, and upper-decile selection are documented and tested.

## Repository hygiene

- [ ] The repository contains source code, tests, portable configurations, documentation, and release metadata.
- [ ] No absolute local paths, usernames, credentials, access tokens, private notes, caches, or build artifacts are present.
- [ ] No generated output directories or large binary/data artifacts are present.
- [ ] Example configurations contain portable relative paths.

## Software quality

- [ ] `python -m pytest` passes.
- [ ] `python -m ruff check .` passes.
- [ ] `python -m build` succeeds.
- [ ] `python scripts/audit_release.py .` passes on a clean export.
- [ ] `spei3d --version` reports the intended release.

## Metadata

- [ ] Version values agree in `pyproject.toml`, `src/spei3d/__init__.py`, `CITATION.cff`, and `CHANGELOG.md`.
- [ ] Author names, software title, repository name, and command-line name are correct.
- [ ] The associated manuscript status is accurate.
- [ ] The release date is correct.

## GitHub publication

- [ ] Repository name is `spei-3d-drought-object-tracking`.
- [ ] The repository is initialized without a second README, license, or `.gitignore`.
- [ ] GitHub Actions completes successfully.
- [ ] The `v1.0.0` release is created from the final verified commit.
- [ ] The release ZIP and SHA-256 file are attached if desired.
- [ ] Repository topics and description are added.
- [ ] The Code availability statement uses the final repository address and release tag.
