# Catalog Import Runbook

This runbook loads the five logical source files in `datasets/raw/` into the shared ScentIQ catalog. The importer writes only rows with `owner_user_id IS NULL`; member-owned fragrances and member tables are outside its write scope. Run it after the catalog migration has succeeded.

The Fragrantica Kaggle corpus is licensed CC BY-NC-SA 4.0. The licensing of the Parfumo, Luckyscent, `fra_cleaned`, and `fra_perfumes` scrapes remains an operational release question. Do not use these datasets in a commercial environment until that question is resolved.

## Inputs and prerequisites

Install the locked dependencies and materialize Git LFS objects:

```powershell
git lfs pull
pnpm install:all
```

The expected files are:

- `datasets/raw/fragrantica_full_kaggle.zip`
- `datasets/raw/fragrantica_fra_perfumes.zip` (contains two logical sources)
- `datasets/raw/parfumo_data_clean.csv`
- `datasets/raw/final_perfume_data.zip`

Record input hashes before an import. Keep the resulting report with the change record; `datasets/reports/` is intentionally ignored by Git.

```powershell
Get-FileHash datasets/raw/fragrantica_full_kaggle.zip -Algorithm SHA256
Get-FileHash datasets/raw/fragrantica_fra_perfumes.zip -Algorithm SHA256
Get-FileHash datasets/raw/parfumo_data_clean.csv -Algorithm SHA256
Get-FileHash datasets/raw/final_perfume_data.zip -Algorithm SHA256
```

PostgreSQL 18 with `pg_trgm` must be available. Set `SCENTIQ_ENV`, `DATABASE_URL`, and `CORS_ORIGINS` in the process environment without writing credentials to a file or shell history.

## Local import

Apply the normal application migration first. Application startup never applies migrations.

```powershell
pnpm api:migrate
```

Run a complete dry run and review `summary.json`, `summary.md`, and `unresolved_matches.csv`. Do not load when unresolved Parfumo and Luckyscent records are at or above one percent, or when the report's source counts and hashes are unexpected.

```powershell
uv run --directory apps/api python -m scentiq_api.catalog_import `
  --raw-dir ../../datasets/raw `
  --report-dir ../../datasets/reports/catalog-import-dry `
  --dry-run
```

Before the first real load, snapshot member-owned and member-data counts or checksums appropriate to the environment. Never put member values in an import report. The following query returns counts only:

```sql
SELECT 'member_brands', count(*) FROM brands WHERE owner_user_id IS NOT NULL
UNION ALL
SELECT 'member_fragrances', count(*) FROM fragrances WHERE owner_user_id IS NOT NULL
UNION ALL
SELECT 'collection_items', count(*) FROM user_collection
UNION ALL
SELECT 'wear_logs', count(*) FROM wear_logs
UNION ALL
SELECT 'wishlists', count(*) FROM wishlists;
```

Run the importer. `--purge-demo-catalog` recognizes only the former fixed demo identifiers, refuses to delete referenced rows, and does not broaden the importer's ownership scope.

```powershell
uv run --directory apps/api python -m scentiq_api.catalog_import `
  --raw-dir ../../datasets/raw `
  --report-dir ../../datasets/reports/catalog-import-real-1 `
  --purge-demo-catalog
```

Rerun the exact command with a new report directory. `catalog_changes` must be zero. The audit row itself is not counted as a catalog change.

```powershell
uv run --directory apps/api python -m scentiq_api.catalog_import `
  --raw-dir ../../datasets/raw `
  --report-dir ../../datasets/reports/catalog-import-real-2 `
  --purge-demo-catalog
```

`--only` is for an explicitly reviewed recovery or diagnostic load, not the standard full import. Disappeared source records and shared fragrances remain in place by design; a routine refresh never deletes them.

## Verification

Run these checks after both real loads:

```sql
SELECT count(*) AS shared_fragrances
FROM fragrances
WHERE owner_user_id IS NULL;

SELECT source, count(*)
FROM fragrance_sources
GROUP BY source
ORDER BY source;

SELECT source, source_record_id, count(*)
FROM fragrance_sources
GROUP BY source, source_record_id
HAVING count(*) > 1;

SELECT brand_id, lower(name), concentration, release_year, gender, count(*)
FROM fragrances
WHERE owner_user_id IS NULL
GROUP BY brand_id, lower(name), concentration, release_year, gender
HAVING count(*) > 1;

SELECT status, count(*)
FROM catalog_import_runs
GROUP BY status
ORDER BY status;
```

The two duplicate queries must return no rows. Repeat the pre-import member counts/checksums and require an exact match. Spot-check source identity, details, children, and similarities for records from more than one source. A successful import can then seed the demo member's collection with real shared rows:

```powershell
pnpm api:seed
```

## Azure development import

The normal deployment workflow must first apply the migration through the gated migration job. Confirm that the PostgreSQL server configuration contains `azure.extensions=PG_TRGM` and that the migration execution succeeded before opening database access for an operator import.

Stop if you do not have all of the following:

- an approved Azure identity with read access to the versionless database URL secret;
- permission to create and delete a firewall rule on the development PostgreSQL server;
- the reviewed source archives and their recorded hashes; and
- an approved change window and a current recovery point.

Use environment-specific values rather than copying credentials into the command. Determine the operator's current public IPv4 address through an approved organizational method, and review every target before mutation:

```powershell
$catalogResourceGroup = '<development-resource-group>'
$catalogServer = '<development-postgres-server>'
$catalogFirewallRule = "catalog-import-$([DateTime]::UtcNow.ToString('yyyyMMddHHmmss'))"
$catalogOperatorIp = '<approved-operator-public-ipv4>'

az postgres flexible-server firewall-rule create `
  --resource-group $catalogResourceGroup `
  --name $catalogServer `
  --rule-name $catalogFirewallRule `
  --start-ip-address $catalogOperatorIp `
  --end-ip-address $catalogOperatorIp
```

Retrieve the database URL into the current process using the approved secret-access procedure, require TLS, run the same dry run and two real imports shown above, and execute the verification SQL. Do not print the URL. Remove the temporary rule in a `finally` block or immediately after any failure:

```powershell
az postgres flexible-server firewall-rule delete `
  --resource-group $catalogResourceGroup `
  --name $catalogServer `
  --rule-name $catalogFirewallRule `
  --yes
```

Confirm the rule is absent before closing the change. Retain only hashes, aggregate counts, audit run identifiers, sanitized verification output, and timing; never retain the database URL or member values.

## Failure and rollback boundaries

The catalog load is one database transaction. A load failure rolls back catalog writes and records a failed audit run separately. Correct the source or code defect, review the new dry-run report, and rerun.

Do not use an Alembic downgrade to undo imported data. The schema downgrade is for migration reversibility before production use; imported note identities can legitimately share a display name, so a post-import downgrade may require cleanup and a separately reviewed recovery plan. After a committed import, rollback means restoring PostgreSQL to the approved pre-import recovery point or applying a forward corrective import. Either action affects the entire database and therefore requires explicit owner approval and member-data impact review.

Never manually delete shared rows merely because a source disappears. Never delete or rewrite a member-owned row or a member table as part of catalog recovery.
