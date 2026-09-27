from __future__ import annotations

import csv
import json
from pathlib import Path

from scentiq_api.catalog_import.merge import build_canonical_catalog
from scentiq_api.catalog_import.report import write_catalog_report
from scentiq_api.catalog_import.types import SourceRecord


def _record(source: str, source_id: str, *, gender: str | None = "female") -> SourceRecord:
    return SourceRecord(
        source=source,  # type: ignore[arg-type]
        source_record_id=source_id,
        source_url=None,
        name="Scent",
        brand="House",
        brand_key="house",
        name_key="scent",
        gender=gender,
    )


def test_report_writes_inspectable_json_markdown_and_unresolved_csv(tmp_path: Path) -> None:
    first = _record("fragrantica", "1", gender="female")
    second = _record("fragrantica", "2", gender="male")
    ambiguous = _record("parfumo", "house/scent", gender=None)
    catalog = build_canonical_catalog([first, second, ambiguous], {}, {})

    report = write_catalog_report(
        catalog,
        tmp_path,
        source_counts={"fragrantica": 2, "parfumo": 1, "luckyscent": 0},
        rejected_counts={"parfumo": 0},
        inputs={"fragrantica": {"sha256": "abc", "rows": 2}},
    )

    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert summary["canonical_fragrances"] == 2
    assert summary["unresolved_matches"] == 1
    assert summary["unresolved_cross_source_percent"] == 100.0
    assert summary["excluded_attributes"]["occasions"]["reason"]
    assert summary["excluded_attributes"]["occasions"]["coverage_count"] == 0
    assert report == summary
    assert "Canonical fragrances: 2" in (tmp_path / "summary.md").read_text(encoding="utf-8")
    with (tmp_path / "unresolved_matches.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["source_record_id"] == "house/scent"
    assert rows[0]["candidate_source_ids"] == "1|2"
