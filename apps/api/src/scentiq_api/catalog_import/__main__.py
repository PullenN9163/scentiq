from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg
from sqlalchemy.engine import make_url

from scentiq_api.catalog_import.load import LoadResult, load_catalog
from scentiq_api.catalog_import.match import load_aliases_csv
from scentiq_api.catalog_import.merge import build_canonical_catalog
from scentiq_api.catalog_import.readers import (
    read_fra_archive,
    read_fragrantica_archive,
    read_luckyscent_archive,
    read_parfumo_file,
)
from scentiq_api.catalog_import.report import write_catalog_report
from scentiq_api.catalog_import.types import RejectedRecord, SourceName, SourceRecord
from scentiq_api.config import Settings

_SOURCES: tuple[SourceName, ...] = (
    "fragrantica",
    "fra_cleaned",
    "fra_perfumes",
    "parfumo",
    "luckyscent",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _psycopg_url(database_url: str) -> str:
    parsed = make_url(database_url).set(drivername="postgresql")
    return parsed.render_as_string(hide_password=False)


def _streams(raw_dir: Path) -> tuple[Iterator[SourceRecord | RejectedRecord], ...]:
    paths = (
        raw_dir / "fragrantica_full_kaggle.zip",
        raw_dir / "fragrantica_fra_perfumes.zip",
        raw_dir / "parfumo_data_clean.csv",
        raw_dir / "final_perfume_data.zip",
    )
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError("missing catalog inputs: " + ", ".join(missing))
    return (
        read_fragrantica_archive(paths[0]),
        read_fra_archive(paths[1]),
        read_parfumo_file(paths[2]),
        read_luckyscent_archive(paths[3]),
    )


def _read_records(
    raw_dir: Path, selected: set[SourceName]
) -> tuple[list[SourceRecord], Counter[str], Counter[str]]:
    records: list[SourceRecord] = []
    source_counts: Counter[str] = Counter()
    rejected_counts: Counter[str] = Counter()
    for stream in _streams(raw_dir):
        for item in stream:
            if item.source not in selected:
                continue
            source_counts[item.source] += 1
            if isinstance(item, RejectedRecord):
                rejected_counts[item.source] += 1
            else:
                records.append(item)
    return records, source_counts, rejected_counts


def _input_manifest(raw_dir: Path, source_counts: Counter[str]) -> dict[str, dict[str, Any]]:
    paths = {
        "fragrantica_archive": raw_dir / "fragrantica_full_kaggle.zip",
        "fra_archive": raw_dir / "fragrantica_fra_perfumes.zip",
        "parfumo_file": raw_dir / "parfumo_data_clean.csv",
        "luckyscent_archive": raw_dir / "final_perfume_data.zip",
    }
    rows = {
        "fragrantica_archive": source_counts["fragrantica"],
        "fra_archive": source_counts["fra_cleaned"] + source_counts["fra_perfumes"],
        "parfumo_file": source_counts["parfumo"],
        "luckyscent_archive": source_counts["luckyscent"],
    }
    return {
        name: {"path": str(path), "sha256": _sha256(path), "rows": rows[name]}
        for name, path in paths.items()
    }


def _existing_sources(connection: psycopg.Connection[Any]) -> dict[tuple[str, str], UUID]:
    with connection.cursor() as cursor:
        cursor.execute("SELECT source,source_record_id,fragrance_id FROM fragrance_sources")
        rows = cursor.fetchall()
    connection.commit()
    return {(str(source), str(record_id)): fragrance_id for source, record_id, fragrance_id in rows}


def _write_load_report(report_dir: Path, result: LoadResult) -> None:
    payload = {
        "run_id": str(result.run_id),
        "catalog_changes": result.catalog_changes,
        "counts": result.counts,
    }
    (report_dir / "load.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines = [
        "# Catalog load report",
        "",
        f"- Run id: {result.run_id}",
        f"- Catalog changes: {result.catalog_changes:,}",
        "",
        "## Counts",
        "",
        *(f"- {key}: {value:,}" for key, value in sorted(result.counts.items())),
    ]
    (report_dir / "load.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import the source-backed shared fragrance catalog"
    )
    repository_root = Path(__file__).parents[5]
    parser.add_argument("--raw-dir", type=Path, default=repository_root / "datasets" / "raw")
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=repository_root / "datasets" / "reports" / "catalog-import",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--only", action="append", choices=_SOURCES)
    parser.add_argument("--purge-demo-catalog", action="store_true")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    selected = set(args.only or _SOURCES)
    records, source_counts, rejected_counts = _read_records(args.raw_dir, selected)
    repository_root = Path(__file__).parents[5]
    brand_aliases = load_aliases_csv(
        repository_root / "datasets" / "mappings" / "brand_aliases.csv"
    )
    accord_aliases = load_aliases_csv(
        repository_root / "datasets" / "mappings" / "accord_aliases.csv"
    )
    manifest = _input_manifest(args.raw_dir, source_counts)

    connection: psycopg.Connection[Any] | None = None
    existing: dict[tuple[str, str], UUID] = {}
    if not args.dry_run:
        settings = Settings()
        connection = psycopg.connect(_psycopg_url(settings.database_url_value))
        existing = _existing_sources(connection)
    try:
        catalog = build_canonical_catalog(
            records,
            brand_aliases,
            existing,
            accord_aliases=accord_aliases,
        )
        summary = write_catalog_report(
            catalog,
            args.report_dir,
            source_counts=source_counts,
            rejected_counts=rejected_counts,
            inputs=manifest,
        )
        if not args.only and summary["unresolved_cross_source_percent"] >= 1:
            raise RuntimeError("unresolved Parfumo + Luckyscent matches must remain below 1%")
        if args.dry_run:
            print(json.dumps({"dry_run": True, **summary}, sort_keys=True))
            return 0
        assert connection is not None
        result = load_catalog(
            connection,
            catalog,
            inputs=manifest,
            purge_demo_catalog=args.purge_demo_catalog,
        )
        _write_load_report(args.report_dir, result)
        print(
            json.dumps(
                {
                    "run_id": str(result.run_id),
                    "catalog_changes": result.catalog_changes,
                    "counts": result.counts,
                },
                sort_keys=True,
            )
        )
        return 0
    finally:
        if connection is not None:
            connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
