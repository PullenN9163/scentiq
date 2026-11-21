"""Compact ranked discovery pool carried in the recommendation snapshot.

The home worker ranks up to ``DISCOVERY_CANDIDATE_POOL`` catalog candidates for each
discovery mode. The unfiltered feed serves only the head of each ranking, but a
filtered request (gender, family, season, accord, minimum value) used to score the
catalog again in the request path. The pool stores a deeper ranked prefix in a form
that carries every attribute those filters read, so the API can filter and page it
with the same semantics as ``FragranceRepository.search`` and rebuild the same
``DiscoveryResult`` the live path returns.

The pool is only ever used when it can answer *exactly*; otherwise the caller falls
back to the live path. See ``pool_can_answer`` for the exactness rule.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from scentiq_api.hybrid.contracts import HybridFragrance
from scentiq_api.schemas.catalog import FragranceSummary
from scentiq_api.schemas.discovery import DiscoveryMode, DiscoveryResult

POOL_VERSION = 1
DISCOVERY_POOL_DEPTH = 400
FACET_KINDS = ("gender", "family", "season", "accord")

AFFINITY_POSITIVE = "Personal taste fit from explicit preferences and rated scent profiles."
AFFINITY_NEGATIVE = "Some recorded scent signals conflict with your personal taste."
# Summary fields that are required but nullable; the pool drops them when null.
_NULLABLE_SUMMARY_FIELDS = (
    "concentration",
    "release_year",
    "image_blob_path",
    "longevity_score",
    "projection_level",
)
LIMITED_EVIDENCE = "Limited catalog evidence; compare the fragrance details before deciding."


@dataclass(frozen=True)
class ScoredDiscovery:
    """A ranked discovery result plus the unrounded inputs its reasons were built from."""

    result: DiscoveryResult
    taste: float
    expansion: float
    risk: float
    affinity: float


def _reasons(
    taste_pct: int,
    expansion_pct: int,
    risk_pct: int,
    season: str | None,
    season_fit: float | None,
    affinity_sign: int,
    evidence: float,
) -> list[str]:
    reasons = [
        f"{taste_pct}% match to positive taste signals; unrated ownership is weak evidence.",
        f"{expansion_pct}% of recorded profile signals add collection variety.",
        f"{risk_pct}% nearest-profile redundancy risk.",
    ]
    if season_fit is not None:
        reasons.append(f"Recorded {season} suitability: {round(season_fit * 100)}%.")
    if affinity_sign > 0:
        reasons.append(AFFINITY_POSITIVE)
    elif affinity_sign < 0:
        reasons.append(AFFINITY_NEGATIVE)
    if evidence < 0.5:
        reasons.append(LIMITED_EVIDENCE)
    return reasons


def universe_facet_counts(candidates: list[HybridFragrance]) -> dict[str, dict[str, int]]:
    """Count candidates per facet value, keyed the way the catalog filters match them."""
    counts: dict[str, dict[str, int]] = {kind: {} for kind in FACET_KINDS}
    for candidate in candidates:
        values: dict[str, set[str]] = {
            "gender": {candidate.fragrance.gender} if candidate.fragrance.gender else set(),
            "family": {candidate.family.lower()} if candidate.family else set(),
            "season": set(candidate.seasons),
            "accord": {name.lower() for name in candidate.accord_names},
        }
        for kind, found in values.items():
            for value in found:
                counts[kind][value] = counts[kind].get(value, 0) + 1
    return counts


def build_discovery_pool(
    *,
    candidates: list[HybridFragrance],
    catalog_facets: dict[str, dict[str, int]] | None,
    universe_limit: int,
    ranked: dict[str, list[ScoredDiscovery]],
    depth: int = DISCOVERY_POOL_DEPTH,
) -> dict[str, Any]:
    """Serialize the top ``depth`` ranked rows per list.

    ``ranked`` is keyed ``"mode"`` (balance, taste, explore) or ``"seasonal:<season>"``.
    """
    by_id = {candidate.fragrance.id: candidate for candidate in candidates}
    vocabulary: dict[str, int] = {}
    fragrances: dict[str, dict[str, Any]] = {}
    brands: dict[str, dict[str, Any]] = {}
    lists: dict[str, dict[str, Any]] = {}
    for key, scored in ranked.items():
        rows: list[list[Any]] = []
        for item in scored[:depth]:
            result = item.result
            identifier = str(result.fragrance.id)
            if identifier not in fragrances:
                candidate = by_id[result.fragrance.id]
                indexes = sorted(
                    {
                        vocabulary.setdefault(name.lower(), len(vocabulary))
                        for name in candidate.accord_names
                    }
                )
                summary = result.fragrance.model_dump(
                    mode="json", exclude_none=True, exclude={"brand"}
                )
                if not summary.get("is_custom"):
                    summary.pop("is_custom", None)
                brand_id = str(result.fragrance.brand.id)
                brands.setdefault(brand_id, result.fragrance.brand.model_dump(mode="json"))
                fragrances[identifier] = {
                    "f": summary,
                    "b": brand_id,
                    "a": indexes,
                    "s": candidate.seasons,
                    "v": candidate.price_value,
                }
            rows.append(
                [
                    identifier,
                    result.taste_match,
                    result.collection_expansion,
                    result.redundancy_risk,
                    result.score,
                    result.evidence_coverage,
                    round(item.taste * 100),
                    round(item.expansion * 100),
                    round(item.risk * 100),
                    (item.affinity > 0) - (item.affinity < 0),
                ]
            )
        lists[key] = {"rows": rows, "full": len(scored) <= depth}

    universe_complete = len(candidates) < universe_limit
    complete_facets: dict[str, list[str]] = {kind: [] for kind in FACET_KINDS}
    if catalog_facets is not None:
        in_universe = universe_facet_counts(candidates)
        for kind in FACET_KINDS:
            catalog_counts = catalog_facets.get(kind, {})
            complete_facets[kind] = sorted(
                value
                for value, count in in_universe[kind].items()
                if catalog_counts.get(value, 0) == count
            )
    return {
        "version": POOL_VERSION,
        "depth": depth,
        "universe_complete": universe_complete,
        "complete_facets": complete_facets,
        "accords": list(vocabulary),
        "brands": brands,
        "fragrances": fragrances,
        "lists": lists,
    }


@dataclass(frozen=True)
class PoolFilters:
    gender: str | None = None
    family: str | None = None
    season: str | None = None
    accord: str | None = None
    minimum_value: float | None = None


def pool_can_answer(pool: dict[str, Any], filters: PoolFilters) -> bool:
    """Whether filtering the pool reproduces the live path's candidate set.

    The live path applies the filters in SQL and *then* keeps the 2,000 most popular
    matches. The pool is built from the 2,000 most popular candidates overall, so it
    holds every live candidate only when the matching set cannot extend past it:
    either the whole catalog fit in that pool, or at least one requested facet
    (gender, family, season, accord) matched exactly as many catalog fragrances as
    pool candidates. A minimum-value filter alone cannot be proven this way.
    """
    if pool.get("universe_complete") is True:
        return True
    complete = pool.get("complete_facets")
    if not isinstance(complete, dict):
        return False
    requested = {
        "gender": filters.gender,
        "family": filters.family.lower() if filters.family else None,
        "season": filters.season,
        "accord": filters.accord.lower() if filters.accord else None,
    }
    for kind, value in requested.items():
        if value is None:
            continue
        values = complete.get(kind)
        if isinstance(values, list) and value in values:
            return True
    return False


def pool_rows(
    payload: dict[str, object],
    *,
    mode: DiscoveryMode,
    season: str | None,
    filters: PoolFilters,
) -> tuple[list[DiscoveryResult], bool] | None:
    """Filtered, ranked pool rows and whether they are the complete ranking.

    ``season`` is the season a seasonal list is keyed on, or ``None`` for the other
    modes. ``filters.season`` is the season the request filters on; for the seasonal
    mode the two coincide. Returns ``None`` when the pool is absent, malformed,
    incompatible or cannot answer exactly, so the caller uses the live path.
    """
    pool = payload.get("discovery_pool")
    if not isinstance(pool, dict) or pool.get("version") != POOL_VERSION:
        return None
    if not pool_can_answer(pool, filters):
        return None
    try:
        key = f"seasonal:{season}" if mode == "seasonal" else mode
        lists = pool["lists"]
        entry = lists.get(key)
        if not isinstance(entry, dict):
            return None
        fragrances = pool["fragrances"]
        vocabulary: list[str] = pool["accords"]
        wanted_accord = (
            vocabulary.index(filters.accord.lower())
            if filters.accord and filters.accord.lower() in vocabulary
            else None
        )
        family = filters.family.lower() if filters.family else None
        summaries: dict[str, FragranceSummary] = {}
        results: list[DiscoveryResult] = []
        for row in entry["rows"]:
            identifier, taste, expansion, risk, score, evidence, tp, ep, rp, sign = row
            data = fragrances[identifier]
            summary_data = data["f"]
            if filters.gender and summary_data.get("gender") != filters.gender:
                continue
            if family and (summary_data.get("olfactory_family") or "").lower() != family:
                continue
            seasons: dict[str, float] = data["s"]
            if filters.season and filters.season not in seasons:
                continue
            if filters.accord and wanted_accord not in data["a"]:
                continue
            if filters.minimum_value is not None and (
                data["v"] is None or data["v"] < filters.minimum_value
            ):
                continue
            summary = summaries.get(identifier)
            if summary is None:
                summary = summaries[identifier] = FragranceSummary.model_validate(
                    {
                        **dict.fromkeys(_NULLABLE_SUMMARY_FIELDS),
                        **summary_data,
                        "brand": pool["brands"][data["b"]],
                    }
                )
            fit_season = filters.season if filters.season else season
            season_fit = seasons.get(fit_season, 0.0) if fit_season else None
            results.append(
                DiscoveryResult(
                    fragrance=summary,
                    taste_match=taste,
                    collection_expansion=expansion,
                    redundancy_risk=risk,
                    score=score,
                    mode=mode,
                    season_fit=season_fit,
                    evidence_coverage=evidence,
                    reasons=_reasons(tp, ep, rp, fit_season, season_fit, sign, evidence),
                )
            )
        return results, entry["full"] is True
    except ValidationError, KeyError, TypeError, ValueError, AttributeError, IndexError:
        return None
