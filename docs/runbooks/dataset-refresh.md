# Dataset refresh

The `Refresh datasets` workflow keeps a current copy of the Fragrantica catalogue dataset that [Le Decanteur publishes on Kaggle](https://www.kaggle.com/datasets/ledecanteur/fragrantica-perfumes) in the `datasets` Blob container of `scentiqstrgdevus`. It stores the raw release only; loading it into the PostgreSQL catalogue is separate, future work.

## How it runs

The workflow runs every Monday at 06:17 UTC and on demand. GitHub runs scheduled and manually dispatched workflows only from the default branch, so it is active once the workflow file reaches `main`.

Each run:

1. reads `fragrantica/latest.json`, the manifest of the stored copy;
2. asks Kaggle for the published version number and stops if it is not newer;
3. downloads that exact version, so the archive matches the version checked;
4. validates it: the archive opens, contains `perfumes.jsonl`, `perfumes.csv` and `SCHEMA.md`, every member passes its CRC check, every record parses and has an `id`, `name` and `brand`, and the record count has not fallen by more than 10% since the stored copy; and
5. uploads the archive and manifest under `fragrantica/v{N}/`, then moves `fragrantica/latest.json` to the new manifest.

A release that fails validation is not uploaded, the stored copy is untouched, and the run fails so it shows up in the Actions tab. Kaggle needs no credentials for this public dataset.

## Blob layout

```text
datasets/
  fragrantica/
    latest.json                        manifest of the current copy
    v3/fragrantica-perfumes.zip        the release as published
    v3/manifest.json                   version, sha256, bytes, record count, licence
```

Blob versioning and fourteen-day soft delete apply, so a replaced or deleted blob can be recovered.

## Access

The workflow signs in as the GitHub deployment identity through the `development` environment's federated credential. That identity holds Storage Blob Data Contributor on the `datasets` container only, declared in `infra/main.bicep` and enforced by `infra/tests/Test-CompiledInfrastructure.ps1`. The container and the role assignment are created by the `Deploy development` workflow, which must run once before the first refresh.

## Operating it

Run a refresh now:

```powershell
gh workflow run refresh-datasets.yml --repo PullenN9163/scentiq
```

Check what is stored:

```powershell
az storage blob download --auth-mode login --account-name scentiqstrgdevus --container-name datasets --name fragrantica/latest.json --file latest.json
```

Run the check locally without touching Azure; a missing manifest means nothing is stored:

```powershell
uv run --directory apps/api python -m scentiq_api.dataset_refresh --current-manifest latest.json --output-dir dataset
```

If a legitimate release is rejected for losing too many records, confirm the drop against the Kaggle page, then store it by running the local command with `--current-manifest` pointing at a missing file and uploading the output as step 5 describes.

## Licence

The dataset is licensed [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/). It may not be used commercially; anything that displays it must credit Le Decanteur and Fragrantica; and derived datasets that are shared must carry the same licence. Each manifest records the licence reported by Kaggle, so a licence change is visible in the stored copy.
