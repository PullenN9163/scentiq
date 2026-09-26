from __future__ import annotations

import csv
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from scentiq_api.catalog_import.merge import CanonicalCatalog

_EXCLUDED_ATTRIBUTE_COUNTS = {
    "ai_summary": (12788, "below the 20% inclusion threshold and third-party generated text"),
    "rating_histogram": (121232, "average and vote count preserve the supported signal"),
    "longevity_histogram": (75740, "average and vote count preserve the supported signal"),
    "sillage_histogram": (78392, "average and vote count preserve the supported signal"),
    "occasions": (0, "no source provides occasion data"),
    "prices": (0, "no source provides price data"),
}


def _excluded_attributes(total: int) -> dict[str, dict[str, str | int | float]]:
    return {
        name: {
            "coverage_count": count,
            "coverage_percent": round(count / total * 100, 4) if total else 0.0,
            "reason": reason,
        }
        for name, (count, reason) in _EXCLUDED_ATTRIBUTE_COUNTS.items()
    }


def _coverage(catalog: CanonicalCatalog) -> dict[str, dict[str, int | float]]:
    total = len(catalog.fragrances)
    fields = (
        "country",
        "concentration",
        "release_year",
        "gender",
        "description",
        "olfactory_family",
        "product_line",
        "image_url",
        "rating_average",
        "popularity_score",
        "longevity_score",
        "projection_level",
        "notes",
        "accords",
        "perfumers",
        "seasons",
        "community",
        "similarities",
    )
    result: dict[str, dict[str, int | float]] = {}
    for field_name in fields:
        count = sum(
            getattr(fragrance, field_name) not in (None, (), {}) for fragrance in catalog.fragrances
        )
        result[field_name] = {
            "count": count,
            "percent": round(count / total * 100, 4) if total else 0.0,
        }
    return result


def write_catalog_report(
    catalog: CanonicalCatalog,
    report_dir: Path,
    *,
    source_counts: Mapping[str, int],
    rejected_counts: Mapping[str, int],
    inputs: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    report_dir.mkdir(parents=True, exist_ok=True)
    cross_source_rows = source_counts.get("parfumo", 0) + source_counts.get("luckyscent", 0)
    unresolved = len(catalog.unresolved)
    summary: dict[str, Any] = {
        "inputs": dict(inputs),
        "source_counts": dict(source_counts),
        "rejected_counts": dict(rejected_counts),
        "canonical_fragrances": len(catalog.fragrances),
        "unresolved_matches": unresolved,
        "unresolved_cross_source_percent": round(unresolved / cross_source_rows * 100, 4)
        if cross_source_rows
        else 0.0,
        "match_rule_counts": catalog.rule_counts,
        "attribute_coverage": _coverage(catalog),
        "excluded_attributes": _excluded_attributes(len(catalog.fragrances)),
    }
    (report_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    lines = [
        "# Catalog import report",
        "",
        f"- Canonical fragrances: {len(catalog.fragrances):,}",
        f"- Unresolved matches: {unresolved:,}",
        (
            "- Unresolved Parfumo + Luckyscent rate: "
            f"{summary['unresolved_cross_source_percent']:.4f}%"
        ),
        "",
        "## Source rows",
        "",
    ]
    lines.extend(
        f"- {source}: {count:,} ({rejected_counts.get(source, 0):,} rejected)"
        for source, count in sorted(source_counts.items())
    )
    lines.extend(["", "## Match rules", ""])
    lines.extend(f"- {rule}: {count:,}" for rule, count in sorted(catalog.rule_counts.items()))
    lines.extend(["", "## Excluded attributes", ""])
    lines.extend(
        f"- {name}: {details['coverage_count']:,} "
        f"({details['coverage_percent']:.4f}%) — {details['reason']}"
        for name, details in summary["excluded_attributes"].items()
    )
    (report_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    with (report_dir / "unresolved_matches.csv").open("w", encoding="utf-8", newline="") as handle:
        fieldnames = (
            "source",
            "source_record_id",
            "raw_brand",
            "raw_name",
            "reason",
            "candidate_source_ids",
        )
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in catalog.unresolved:
            writer.writerow(
                {
                    "source": item.record.source,
                    "source_record_id": item.record.source_record_id,
                    "raw_brand": item.record.brand or "",
                    "raw_name": item.record.name or "",
                    "reason": item.reason,
                    "candidate_source_ids": "|".join(item.candidate_source_ids),
                }
            )
    return summary
