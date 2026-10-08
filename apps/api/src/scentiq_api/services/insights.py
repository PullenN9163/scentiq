"""Collection insights computed from persisted collection and wear history."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from itertools import combinations
from uuid import UUID

from sqlalchemy import Row

from scentiq_api.repositories import InsightsRepository
from scentiq_api.schemas import (
    CollectionInsightsResponse,
    CountSlice,
    MostWornEntry,
    WeightedSlice,
)
from scentiq_api.schemas.insights import NoteFrequency, OwnedInsightEntry, RedundancyPair
from scentiq_api.services.layer_stack_scoring import overlap

RECENT_WINDOW = timedelta(days=30)


def _weighted(rows: list[Row[tuple[str, int]]] | list[tuple[str, int]]) -> list[WeightedSlice]:
    total = sum(count for _, count in rows)
    if total == 0:
        return []
    return [
        WeightedSlice(label=label, count=count, share=round(count / total, 3))
        for label, count in rows
    ]


class InsightsService:
    def __init__(self, repository: InsightsRepository) -> None:
        self._repository = repository

    def for_user(self, user_id: UUID, *, now: datetime | None = None) -> CollectionInsightsResponse:
        reference = now or datetime.now(UTC)
        since = reference - RECENT_WINDOW

        (
            total_items,
            owned_items,
            wishlist_items,
            retired_items,
            price_total,
            priced_items,
        ) = self._repository.collection_totals(user_id)
        average_rating, rated_items = self._repository.rating_summary(user_id)
        total_wears, recent_wears, distinct_worn = self._repository.wear_totals(user_id, since)
        owned = self._repository.owned_items(user_id)
        history = self._repository.item_wear_history(user_id)
        entries = []
        for item in owned:
            count, last = history.get(item.id, (0, None))
            entries.append(
                OwnedInsightEntry(
                    collection_item_id=item.id,
                    fragrance_id=item.fragrance_id,
                    fragrance_name=item.fragrance.name,
                    brand_name=item.fragrance.brand.name,
                    wear_count=count,
                    last_worn_at=last,
                    user_rating=item.user_rating,
                    cost_per_wear=(
                        format((item.purchase_price / count).quantize(Decimal("0.01")), "f")
                        if count and item.purchase_price is not None
                        else None
                    ),
                )
            )
        neglected = [
            entry
            for entry in entries
            if entry.last_worn_at is None or entry.last_worn_at.replace(tzinfo=UTC) < since
        ]
        neglected.sort(
            key=lambda entry: (
                entry.last_worn_at is not None,
                entry.last_worn_at.replace(tzinfo=UTC) if entry.last_worn_at else reference,
                entry.fragrance_name,
            )
        )
        note_counts: Counter[tuple[str, str]] = Counter()
        for item in owned:
            note_counts.update({(link.note.name, link.stage) for link in item.fragrance.note_links})
        note_items = sum(bool(item.fragrance.note_links) for item in owned)
        redundancy = []
        # Metadata comparisons are bounded; no all-catalog or wear-log N+1 joins.
        for first, second in combinations(owned[:200], 2):
            a = {link.accord.slug: float(link.weight) for link in first.fragrance.accord_links}
            b = {link.accord.slug: float(link.weight) for link in second.fragrance.accord_links}
            similarity = overlap(a, b)
            if similarity >= 0.65:
                redundancy.append(
                    RedundancyPair(
                        first_id=first.fragrance_id,
                        first_name=first.fragrance.name,
                        second_id=second.fragrance_id,
                        second_name=second.fragrance.name,
                        overlap=round(similarity, 4),
                        shared_accords=sorted(set(a) & set(b)),
                    )
                )
        season_strength = {
            season: max(
                (
                    float(link.weight)
                    for item in owned
                    for link in item.fragrance.seasons
                    if link.season == season
                ),
                default=0,
            )
            for season in ("spring", "summer", "fall", "winter")
        }
        season_items = sum(bool(item.fragrance.seasons) for item in owned)

        return CollectionInsightsResponse(
            total_items=total_items,
            owned_items=owned_items,
            wishlist_items=wishlist_items,
            retired_items=retired_items,
            custom_items=self._repository.custom_item_count(user_id),
            # Null rather than "0.00" when nothing has a recorded price, so the
            # UI can distinguish "no data" from "free".
            total_purchase_value=(
                format(Decimal(price_total).quantize(Decimal("0.01")), "f")
                if price_total is not None
                else None
            ),
            priced_items=priced_items,
            average_rating=round(float(average_rating), 2) if average_rating is not None else None,
            rated_items=rated_items,
            total_wears=total_wears,
            wears_last_30_days=recent_wears,
            distinct_fragrances_worn=distinct_worn,
            most_worn=[
                MostWornEntry(
                    collection_item_id=item_id,
                    fragrance_id=fragrance_id,
                    fragrance_name=fragrance_name,
                    brand_name=brand_name,
                    wear_count=wear_count,
                )
                for item_id, fragrance_id, fragrance_name, brand_name, wear_count in (
                    self._repository.most_worn(user_id)
                )
            ],
            accords=_weighted(self._repository.accord_breakdown(user_id)),
            seasons=_weighted(self._repository.season_breakdown(user_id)),
            occasions=_weighted(self._repository.occasion_breakdown(user_id)),
            ownership_types=[
                CountSlice(label=label, count=count)
                for label, count in self._repository.ownership_type_counts(user_id)
            ],
            # Custom entries usually have no accords/seasons/occasions, so the
            # breakdowns above cover only part of the collection. Reporting the
            # remainder keeps the screen honest instead of implying full cover.
            unclassified_items=self._repository.unclassified_item_count(user_id),
            least_worn=sorted(entries, key=lambda entry: (entry.wear_count, entry.fragrance_name))[
                :5
            ],
            neglected=neglected[:5],
            highest_rated=sorted(
                (entry for entry in entries if entry.user_rating is not None),
                key=lambda entry: (
                    -(entry.user_rating or 0),
                    -entry.wear_count,
                    entry.fragrance_name,
                ),
            )[:5],
            cost_per_wear=sorted(
                (entry for entry in entries if entry.cost_per_wear is not None),
                key=lambda entry: (Decimal(entry.cost_per_wear or "0"), entry.fragrance_name),
            )[:10],
            note_frequency=[
                NoteFrequency(
                    label=label, stage=stage, count=count, share=round(count / note_items, 3)
                )
                for (label, stage), count in sorted(
                    note_counts.items(), key=lambda row: (-row[1], row[0])
                )[:30]
            ],
            redundancy_pairs=sorted(redundancy, key=lambda pair: (-pair.overlap, pair.first_name))[
                :8
            ],
            season_coverage_score=round(sum(season_strength.values()) / 4, 3)
            if season_items
            else None,
            season_evidence_coverage=round(season_items / len(owned), 3) if owned else 0,
            season_gaps=[season for season, strength in season_strength.items() if strength < 0.5]
            if season_items
            else [],
            occasion_behavior=_weighted(self._repository.occasion_behavior(user_id)),
        )
