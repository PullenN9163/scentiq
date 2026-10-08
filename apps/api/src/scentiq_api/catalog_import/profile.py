from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import zipfile
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

_MISSING_TEXT = {"", "na", "n/a", "none", "null", "unknown"}
_FRAGRANTICA_ID = re.compile(r"-(\d+)\.html(?:$|[?#])", re.IGNORECASE)
_FAMILY = re.compile(r"\bis an? ([A-Z][A-Za-z-]+(?: [A-Z][A-Za-z-]+){0,3}) fragrance for\b")
_YEAR_TOKEN = re.compile(r"(?<!\d)(?:17|18|19|20)\d{2}(?!\d)")
_CONCENTRATION = re.compile(
    r"\b(?:extrait de parfum|eau de parfum|eau de toilette|eau de cologne|"
    r"perfume oil|solid perfume|after shave|body spray|parfum|extrait|cologne|edp|edt|edc)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CoverageMetric:
    count: int
    percent: float


@dataclass
class SourceProfile:
    rows_read: int = 0
    rows_rejected: int = 0
    rejection_reasons: Counter[str] = field(default_factory=Counter)
    coverage: dict[str, CoverageMetric] = field(default_factory=dict)
    duplicate_record_keys: int = 0
    field_names: list[str] = field(default_factory=list)
    longest_values: dict[str, int] = field(default_factory=dict)
    observations: dict[str, int | float | str | None] = field(default_factory=dict)


@dataclass
class ProfileReport:
    inputs: dict[str, dict[str, int | str]]
    sources: dict[str, SourceProfile]
    final_catalog_candidate_rows: int
    inclusion_threshold_rows: int
    excluded_attributes: dict[str, dict[str, int | float | str]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "inputs": self.inputs,
            "sources": {
                name: {
                    "rows_read": source.rows_read,
                    "rows_rejected": source.rows_rejected,
                    "rejection_reasons": dict(source.rejection_reasons),
                    "coverage": {
                        metric_name: asdict(metric)
                        for metric_name, metric in source.coverage.items()
                    },
                    "duplicate_record_keys": source.duplicate_record_keys,
                    "field_names": source.field_names,
                    "longest_values": source.longest_values,
                    "observations": source.observations,
                }
                for name, source in self.sources.items()
            },
            "final_catalog_candidate_rows": self.final_catalog_candidate_rows,
            "inclusion_threshold_rows": self.inclusion_threshold_rows,
            "excluded_attributes": self.excluded_attributes,
        }


def is_meaningful(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().casefold() not in _MISSING_TEXT
    if isinstance(value, Mapping):
        return bool(value) and any(is_meaningful(item) and item != 0 for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return bool(value) and any(is_meaningful(item) for item in value)
    return True


def valid_year(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        year = int(str(value).strip())
    except ValueError:
        return None
    return year if 1700 <= year <= 2100 else None


def histogram_votes(histogram: object) -> int:
    if not isinstance(histogram, list):
        return 0
    total = 0
    for bucket in histogram:
        if not isinstance(bucket, Mapping):
            continue
        try:
            total += int(bucket.get("count") or 0)
        except TypeError, ValueError:
            continue
    return total


def parse_olfactory_family(description: object) -> str | None:
    if not isinstance(description, str):
        return None
    match = _FAMILY.search(description)
    return match.group(1) if match else None


def coverage(values: Iterable[object], *, total: int) -> CoverageMetric:
    count = sum(is_meaningful(value) for value in values)
    percent = round((count / total * 100) if total else 0.0, 4)
    return CoverageMetric(count=count, percent=percent)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _archive_text_rows(
    archive_path: Path,
    member: str,
    *,
    encoding: str,
    delimiter: str = ",",
) -> Iterator[dict[str, str]]:
    with zipfile.ZipFile(archive_path) as archive, archive.open(member) as raw:
        text = io.TextIOWrapper(raw, encoding=encoding, newline="")
        yield from csv.DictReader(text, delimiter=delimiter)


def _luckyscent_rows(path: Path) -> Iterator[dict[str, str]]:
    with zipfile.ZipFile(path) as archive:
        payload = archive.read("final_perfume_data.csv")
    try:
        text = payload.decode("cp1252")
    except UnicodeDecodeError:
        text = payload.decode("latin-1")
    yield from csv.DictReader(io.StringIO(text, newline=""))


def _fragrantica_rows(path: Path) -> Iterator[dict[str, Any]]:
    with zipfile.ZipFile(path) as archive, archive.open("perfumes.jsonl") as raw:
        text = io.TextIOWrapper(raw, encoding="utf-8")
        for line in text:
            if line.strip():
                value = json.loads(line)
                if isinstance(value, dict):
                    yield value


def _record_id(url: object) -> str | None:
    match = _FRAGRANTICA_ID.search(str(url or ""))
    return match.group(1) if match else None


def _count_duplicate_keys(keys: Iterable[str | None]) -> int:
    counts = Counter(key for key in keys if key is not None)
    return sum(count - 1 for count in counts.values() if count > 1)


def _metric(count: int, total: int) -> CoverageMetric:
    return CoverageMetric(count=count, percent=round((count / total * 100) if total else 0.0, 4))


def _longest(target: dict[str, int], key: str, value: object) -> None:
    if is_meaningful(value):
        target[key] = max(target.get(key, 0), len(str(value).strip()))


def _identity_text_present(value: object) -> bool:
    """Identity labels may literally be named "Unknown"; only blank is absent."""
    return isinstance(value, str) and bool(value.strip())


def _profile_fragrantica(path: Path) -> SourceProfile:
    profile = SourceProfile()
    counts: Counter[str] = Counter()
    ids: list[str | None] = []
    years: list[int] = []
    raw_years: list[int] = []
    families: set[str] = set()
    fields: set[str] = set()

    for row in _fragrantica_rows(path):
        profile.rows_read += 1
        fields.update(row)
        record_id = row.get("id")
        ids.append(str(record_id) if record_id is not None else None)
        if (
            record_id is None
            or not _identity_text_present(row.get("name"))
            or not _identity_text_present(row.get("brand"))
        ):
            profile.rows_rejected += 1
            profile.rejection_reasons["missing_identity"] += 1
            continue

        for key in ("name", "brand", "collection", "description"):
            _longest(profile.longest_values, key, row.get(key))
        if is_meaningful(row.get("gender")):
            counts["official_gender"] += 1
        description = row.get("description")
        if (family := parse_olfactory_family(description)) is not None:
            counts["olfactory_family"] += 1
            families.add(family)
        if is_meaningful(row.get("accords")):
            counts["accords_with_strength"] += 1
        notes_value = row.get("notes")
        notes: Mapping[str, Any] = notes_value if isinstance(notes_value, Mapping) else {}
        tiered = notes.get("tiered", {})
        flat = notes.get("flat", [])
        if is_meaningful(tiered):
            counts["tiered_notes"] += 1
        if is_meaningful(flat):
            counts["flat_notes"] += 1

        rating_value = row.get("rating")
        rating: Mapping[str, Any] = rating_value if isinstance(rating_value, Mapping) else {}
        if is_meaningful(rating.get("average")) and histogram_votes(rating.get("histogram")) > 0:
            counts["rating_with_votes"] += 1
        for source_key, report_key in (
            ("seasons", "season_votes_at_least_5"),
            ("daypart", "daypart_votes_at_least_5"),
            ("community_gender", "perceived_gender_votes_at_least_5"),
        ):
            block = row.get(source_key)
            if isinstance(block, Mapping) and sum(int(value or 0) for value in block.values()) >= 5:
                counts[report_key] += 1
        for source_key, report_key in (
            ("sillage", "sillage_votes_at_least_5"),
            ("longevity", "longevity_votes_at_least_5"),
            ("price_value", "price_value_votes_at_least_5"),
        ):
            block = row.get(source_key)
            if isinstance(block, Mapping) and histogram_votes(block.get("histogram")) >= 5:
                counts[report_key] += 1
        relation = row.get("relation")
        popularity = row.get("popularity")
        magnitude = popularity.get("magnitude") if isinstance(popularity, Mapping) else None
        if is_meaningful(relation):
            counts["relation_counts"] += 1
        if isinstance(magnitude, (int, float)) and magnitude > 0:
            counts["popularity_magnitude"] += 1
        similar_value = row.get("similar")
        similar: Mapping[str, Any] = similar_value if isinstance(similar_value, Mapping) else {}
        if is_meaningful(similar.get("reminds_me_of")):
            counts["reminds_me_of"] += 1
        if is_meaningful(similar.get("also_liked")):
            counts["also_liked"] += 1
        if is_meaningful(row.get("perfumers")):
            counts["perfumers"] += 1
        if is_meaningful(row.get("collection")):
            counts["product_line"] += 1
        if is_meaningful(row.get("picture")) or record_id is not None:
            counts["image_url"] += 1
        if isinstance(row.get("name"), str) and _CONCENTRATION.search(row["name"]):
            counts["concentration_in_name"] += 1
        if is_meaningful(row.get("ai_summary")):
            counts["ai_summary"] += 1
        if any(
            histogram_votes((row.get(key) or {}).get("histogram")) > 0
            for key in ("rating", "longevity", "sillage")
            if isinstance(row.get(key), Mapping)
        ):
            counts["rating_longevity_sillage_histograms"] += 1

        raw_year = row.get("year")
        try:
            if raw_year is not None:
                raw_years.append(int(raw_year))
        except TypeError, ValueError:
            pass
        if (year := valid_year(raw_year)) is not None:
            years.append(year)

    profile.coverage = {
        name: _metric(count, profile.rows_read) for name, count in sorted(counts.items())
    }
    profile.coverage["occasions"] = _metric(0, profile.rows_read)
    profile.duplicate_record_keys = _count_duplicate_keys(ids)
    profile.field_names = sorted(fields)
    profile.observations = {
        "raw_year_min": min(raw_years) if raw_years else None,
        "raw_year_max": max(raw_years) if raw_years else None,
        "valid_year_min": min(years) if years else None,
        "valid_year_max": max(years) if years else None,
        "valid_year_count": len(years),
        "olfactory_family_values": len(families),
    }
    return profile


def _profile_csv_source(
    rows: Iterable[dict[str, str]],
    *,
    coverage_fields: Mapping[str, Callable[[dict[str, str]], object]],
    key: Callable[[dict[str, str]], str | None],
    required: tuple[str, ...],
) -> SourceProfile:
    profile = SourceProfile()
    values: dict[str, list[object]] = defaultdict(list)
    keys: list[str | None] = []
    fields: set[str] = set()
    for row in rows:
        profile.rows_read += 1
        fields.update(row)
        record_key = key(row)
        keys.append(record_key)
        if record_key is None or any(not is_meaningful(row.get(column)) for column in required):
            profile.rows_rejected += 1
            profile.rejection_reasons["missing_identity"] += 1
            continue
        for column in ("Name", "Brand", "Perfume", "Description", "Country", "Concentration"):
            if column in row:
                _longest(profile.longest_values, column, row.get(column))
        for name, getter in coverage_fields.items():
            values[name].append(getter(row))
    accepted = profile.rows_read - profile.rows_rejected
    profile.coverage = {
        name: coverage(items, total=accepted) for name, items in sorted(values.items())
    }
    profile.duplicate_record_keys = _count_duplicate_keys(keys)
    profile.field_names = sorted(fields)
    return profile


def _profile_fra_cleaned(path: Path) -> SourceProfile:
    profile = _profile_csv_source(
        _archive_text_rows(path, "fra_cleaned.csv", encoding="cp1252", delimiter=";"),
        coverage_fields={
            "brand_country": lambda row: row.get("Country"),
            "gender": lambda row: row.get("Gender"),
            "rating": lambda row: row.get("Rating Value"),
            "release_year": lambda row: valid_year(row.get("Year")),
            "tiered_notes": lambda row: [row.get("Top"), row.get("Middle"), row.get("Base")],
            "perfumers": lambda row: [row.get("Perfumer1"), row.get("Perfumer2")],
            "accords": lambda row: [row.get(f"mainaccord{index}") for index in range(1, 6)],
        },
        key=lambda row: _record_id(row.get("url")),
        required=("url",),
    )
    brand_countries: dict[str, set[str]] = defaultdict(set)
    for row in _archive_text_rows(path, "fra_cleaned.csv", encoding="cp1252", delimiter=";"):
        brand = str(row.get("Brand") or "").strip().casefold()
        country = str(row.get("Country") or "").strip()
        if brand and country and country.casefold() not in _MISSING_TEXT:
            brand_countries[brand].add(country)
    profile.observations["brand_country_values"] = len(
        {country for countries in brand_countries.values() for country in countries}
    )
    profile.observations["brands_with_country_conflicts"] = sum(
        len(countries) > 1 for countries in brand_countries.values()
    )
    return profile


def _profile_fra_perfumes(path: Path) -> SourceProfile:
    return _profile_csv_source(
        _archive_text_rows(path, "fra_perfumes.csv", encoding="utf-8"),
        coverage_fields={
            "gender": lambda row: row.get("Gender"),
            "rating": lambda row: row.get("Rating Value"),
            "accords": lambda row: row.get("Main Accords"),
            "perfumers": lambda row: row.get("Perfumers"),
            "description": lambda row: row.get("Description"),
        },
        key=lambda row: _record_id(row.get("url")),
        required=("url", "Name"),
    )


def _profile_parfumo(path: Path) -> SourceProfile:
    profile = _profile_csv_source(
        _plain_csv_rows(path, encoding="utf-8"),
        coverage_fields={
            "release_year": lambda row: valid_year(row.get("Release_Year")),
            "concentration": lambda row: row.get("Concentration"),
            "rating": lambda row: row.get("Rating_Value"),
            "accords": lambda row: row.get("Main_Accords"),
            "tiered_notes": lambda row: [
                row.get("Top_Notes"),
                row.get("Middle_Notes"),
                row.get("Base_Notes"),
            ],
            "perfumers": lambda row: row.get("Perfumers"),
        },
        key=lambda row: _parfumo_key(row.get("URL")),
        required=("URL", "Name", "Brand"),
    )
    brand_in_name = 0
    year_in_name = 0
    for row in _plain_csv_rows(path, encoding="utf-8"):
        name = str(row.get("Name") or "")
        brand = str(row.get("Brand") or "")
        if brand and re.search(rf"(?<!\w){re.escape(brand)}(?!\w)", name, re.IGNORECASE):
            brand_in_name += 1
        if _YEAR_TOKEN.search(name):
            year_in_name += 1
    profile.observations["names_containing_brand"] = brand_in_name
    profile.observations["names_containing_year"] = year_in_name
    return profile


def _plain_csv_rows(path: Path, *, encoding: str) -> Iterator[dict[str, str]]:
    with path.open(encoding=encoding, newline="") as handle:
        yield from csv.DictReader(handle)


def _parfumo_key(url: object) -> str | None:
    marker = "/Perfumes/"
    text = str(url or "")
    if marker not in text:
        return None
    key = text.split(marker, 1)[1].strip("/")
    return key or None


def _profile_luckyscent(path: Path) -> SourceProfile:
    return _profile_csv_source(
        _luckyscent_rows(path),
        coverage_fields={
            "description": lambda row: row.get("Description"),
            "flat_notes": lambda row: row.get("Notes"),
            "image_url": lambda row: row.get("Image URL"),
            "concentration_in_name": lambda row: (
                _CONCENTRATION.search(row.get("Name") or "") is not None
            ),
        },
        key=lambda row: (
            hashlib.sha1(
                f"{str(row.get('Brand') or '').strip().casefold()}|"
                f"{str(row.get('Name') or '').strip().casefold()}".encode()
            ).hexdigest()
            if is_meaningful(row.get("Brand")) and is_meaningful(row.get("Name"))
            else None
        ),
        required=("Name", "Brand"),
    )


def profile_sources(raw_dir: Path) -> ProfileReport:
    paths = {
        "fragrantica_archive": raw_dir / "fragrantica_full_kaggle.zip",
        "fra_archive": raw_dir / "fragrantica_fra_perfumes.zip",
        "parfumo_file": raw_dir / "parfumo_data_clean.csv",
        "luckyscent_archive": raw_dir / "final_perfume_data.zip",
    }
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing raw catalog inputs: {', '.join(missing)}")

    sources = {
        "fragrantica": _profile_fragrantica(paths["fragrantica_archive"]),
        "fra_cleaned": _profile_fra_cleaned(paths["fra_archive"]),
        "fra_perfumes": _profile_fra_perfumes(paths["fra_archive"]),
        "parfumo": _profile_parfumo(paths["parfumo_file"]),
        "luckyscent": _profile_luckyscent(paths["luckyscent_archive"]),
    }
    candidate_rows = (
        sources["fragrantica"].rows_read
        + sources["parfumo"].rows_read
        + sources["luckyscent"].rows_read
    )
    threshold = int(candidate_rows * 0.2)
    fragrantica = sources["fragrantica"]
    excluded = {
        "ai_summary": {
            **asdict(fragrantica.coverage.get("ai_summary", CoverageMetric(0, 0.0))),
            "reason": "below 20% and third-party generated text",
        },
        "rating_longevity_sillage_histograms": {
            **asdict(
                fragrantica.coverage.get(
                    "rating_longevity_sillage_histograms", CoverageMetric(0, 0.0)
                )
            ),
            "reason": "averages and vote counts preserve the supported signal",
        },
        "occasions": {
            "count": 0,
            "percent": 0.0,
            "reason": "no source provides occasion data",
        },
        "prices": {
            "count": 0,
            "percent": 0.0,
            "reason": "no source provides price data",
        },
    }
    return ProfileReport(
        inputs={
            name: {"path": str(path), "bytes": path.stat().st_size, "sha256": _sha256(path)}
            for name, path in paths.items()
        },
        sources=sources,
        final_catalog_candidate_rows=candidate_rows,
        inclusion_threshold_rows=threshold,
        excluded_attributes=excluded,
    )


def write_profile(report: ProfileReport, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile the raw catalog sources")
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = profile_sources(args.raw_dir)
    write_profile(report, args.output)
    print(json.dumps({name: source.rows_read for name, source in report.sources.items()}))


if __name__ == "__main__":
    main()
