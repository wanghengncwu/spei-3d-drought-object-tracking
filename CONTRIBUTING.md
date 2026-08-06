# Contributing

This repository provides a focused research-software workflow for SPEI-based 3-D drought-object tracking. Contributions should preserve the documented scientific definitions, deterministic event-linking behavior, output contracts, and reproducibility safeguards.

## Before opening a change

1. Confirm that the proposed change concerns SPEI input handling, monthly drought-patch identification, temporal linking, object filtering, catalogue generation, sensitivity experiments, metadata, documentation, or testing.
2. Keep examples portable and free of machine-specific paths, credentials, generated outputs, caches, and large binary files.
3. Add or update a synthetic test for every behavioral change.
4. Update the relevant documentation when a configuration field, command, output column, or scientific definition changes.

## Local checks

```bash
python -m pip install -e ".[dev,labels]"
python scripts/verify_release.py
```

## Reporting a problem

Include the software version, Python version, operating system, configuration excerpt, input coordinate names and dimensions, and the complete error message. Use a minimal reproducible example whenever possible.
