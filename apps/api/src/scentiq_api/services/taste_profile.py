"""Shared, inspectable taste learning from explicit preferences and rated experience."""

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from statistics import mean
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from scentiq_api.models import (
    Fragrance,
    FragranceAccord,
    FragranceNote,
    UserCollectionItem,
    UserPreference,
    WearFeedback,
    WearLog,
)
from scentiq_api.models.layer_stacks import LayerStackItem, LayerStackWear
from scentiq_api.models.recommendation_choices import RecommendationFeedback
from scentiq_api.models.taste import UserTasteProfile


def fragrance_features(fragrance: Fragrance) -> set[str]:
    values = {f"accord:{link.accord.slug}" for link in fragrance.accord_links}
    values.update(f"note:{link.note.slug}" for link in fragrance.note_links)
    if fragrance.olfactory_family:
        values.add("family:" + fragrance.olfactory_family.casefold().replace(" ", "-"))
    return values


@dataclass(frozen=True)
class TasteProfile:
    version: str
    features: dict[str, float]
    excluded_ids: frozenset[UUID]
    variety: str

    def affinity(self, fragrance: Fragrance) -> float:
        values = [
            self.features[key] for key in fragrance_features(fragrance) if key in self.features
        ]
        return mean(values) if values else 0.0

    def evidence(self, fragrance: Fragrance) -> list[str]:
        return sorted(key for key in fragrance_features(fragrance) if key in self.features)


class TasteProfileService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def for_user(self, user_id: UUID) -> TasteProfile:
        preferences = self.session.get(UserPreference, user_id)
        collection = list(
            self.session.scalars(
                select(UserCollectionItem)
                .where(UserCollectionItem.user_id == user_id)
                .options(
                    joinedload(UserCollectionItem.fragrance)
                    .selectinload(Fragrance.accord_links)
                    .joinedload(FragranceAccord.accord),
                    joinedload(UserCollectionItem.fragrance)
                    .selectinload(Fragrance.note_links)
                    .joinedload(FragranceNote.note),
                )
            )
        )
        ratings: dict[UUID, list[float]] = defaultdict(list)
        fragrances = {item.fragrance_id: item.fragrance for item in collection}
        # Duplicate bottle/decant rows contribute a single average personal rating.
        item_ratings: dict[UUID, list[float]] = defaultdict(list)
        for item in collection:
            if item.user_rating is not None:
                item_ratings[item.fragrance_id].append(float(item.user_rating))
        for fragrance_id, values in item_ratings.items():
            ratings[fragrance_id].append(mean(values))
        for fragrance_id, rating in self.session.execute(
            select(UserCollectionItem.fragrance_id, WearFeedback.rating)
            .join(WearLog, WearLog.collection_item_id == UserCollectionItem.id)
            .join(WearFeedback, WearFeedback.wear_log_id == WearLog.id)
            .where(WearLog.user_id == user_id, WearFeedback.rating.is_not(None))
        ):
            ratings[fragrance_id].append(float(rating))
        disliked_ids = set(
            self.session.scalars(
                select(RecommendationFeedback.fragrance_id).where(
                    RecommendationFeedback.user_id == user_id,
                    RecommendationFeedback.reason == "dislike_scent",
                )
            )
        )
        for fragrance_id in disliked_ids:
            ratings[fragrance_id].append(1.0)
        for fragrance_id, rating in self.session.execute(
            select(LayerStackItem.fragrance_id, LayerStackWear.rating)
            .join(LayerStackWear, LayerStackWear.stack_id == LayerStackItem.stack_id)
            .where(LayerStackWear.user_id == user_id, LayerStackWear.rating.is_not(None))
        ):
            ratings[fragrance_id].append(float(rating))
        learned: dict[str, list[float]] = defaultdict(list)
        for fragrance_id, values in ratings.items():
            if fragrance_id in fragrances:
                for key in fragrance_features(fragrances[fragrance_id]):
                    learned[key].append((mean(values) - 3) / 2)
        features = {key: round(mean(values), 4) for key, values in learned.items()}
        if preferences:
            for kind, prefix in (("notes", "note"), ("accords", "accord"), ("families", "family")):
                for polarity, value in (("liked", 1.0), ("disliked", -1.0)):
                    features.update(
                        {
                            f"{prefix}:{key}": value
                            for key in getattr(preferences, f"{polarity}_{kind}")
                        }
                    )
        exclusions = frozenset(
            {UUID(value) for value in (preferences.excluded_fragrance_ids if preferences else [])}
            | disliked_ids
        )
        variety = preferences.variety_preference if preferences else "balanced"
        version = hashlib.sha256(
            json.dumps(
                {
                    "features": features,
                    "excluded": sorted(map(str, exclusions)),
                    "variety": variety,
                    "algorithm": "taste-v1",
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()
        cached = self.session.get(UserTasteProfile, user_id)
        if cached is None:
            cached = UserTasteProfile(user_id=user_id, version=version, features=features)
            try:
                with self.session.begin_nested():
                    self.session.add(cached)
                    self.session.flush()
            except IntegrityError:
                # Another request initialized the same member's cache. The derived
                # response remains authoritative; do not roll back the parent request.
                cached = self.session.get(UserTasteProfile, user_id)
                if cached is not None:
                    cached.version, cached.features = version, features
        elif cached.version != version:
            cached.version, cached.features = version, features
        self.session.flush()
        return TasteProfile(version, features, exclusions, variety)
