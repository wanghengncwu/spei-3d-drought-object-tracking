# Reproducibility workflow

## 1. Preserve the input products

Store the precomputed SPEI files outside the GitHub repository. Record the dataset version, variable name, time period, grid, units, preprocessing decisions, and the method used to calculate SPEI.

## 2. Create immutable run configurations

Copy the example YAML files and edit only the required paths and parameters. Preserve the final configuration files with the analysis archive.

## 3. Enable input fingerprints for archival runs

Set:

```yaml
runtime:
  hash_inputs: true
```

This records SHA-256 fingerprints in `run_manifest.json`. Hashing large files increases startup time but provides a strong identity check for archived inputs.

## 4. Validate before execution

```bash
spei3d validate-config --config configs/baseline.yml
spei3d validate-config --config configs/sensitivity.yml
```

## 5. Run the baseline and sensitivity workflows

```bash
spei3d extract --config configs/baseline.yml
spei3d sensitivity --config configs/sensitivity.yml
```

## 6. Preserve the complete output metadata

Do not delete `run_manifest.json`, `run.ok`, the exact YAML configuration, or the software release tag. These files identify the software version, algorithm version, dependencies, input descriptors, parameters, and result summaries.

## 7. Verify the release tree

```bash
python scripts/verify_release.py
```

## 8. Archive a tagged release

Create the Git tag `v1.0.0` from the exact commit used for the manuscript revision. Do not modify or move this tag. Later documentation-only updates should use a new patch release rather than replacing the archived release.
