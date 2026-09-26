from __future__ import annotations

from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload, load_only, selectinload
from sqlalchemy.sql.base import ExecutableOption

from scentiq_api.models import (
    Fragrance,
    FragranceAccord,
    FragranceNote,
    FragranceSimilarity,
    UserCollectionItem,
)
from scentiq_api.repositories.fragrances import FragranceRepository

DISCOVERY_CANDIDATE_POOL = 2_000


def _discovery_options() -> tuple[ExecutableOption, ...]:
    """Load only data consumed by discovery scoring and its result summaries."""
    return (
        load_only(
            Fragrance.id,
            Fragrance.brand_id,
            Fragrance.owner_user_id,
            Fragrance.name,
            Fragrance.concentration,
            Fragrance.release_year,
            Fragrance.image_blob_path,
            Fragrance.image_url,
            Fragrance.gender,
            Fragrance.olfactory_family,
            Fragrance.rating_average,
            Fragrance.rating_count,
            Fragrance.popularity_score,
            Fragrance.longevity_score,
            Fragrance.projection_level,
        ),
        joinedload(Fragrance.brand),
        selectinload(Fragrance.note_links).joinedload(FragranceNote.note),
        selectinload(Fragrance.accord_links).joinedload(FragranceAccord.accord),
    )


class DiscoveryRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def owned(self, user_id: UUID) -> list[Fragrance]:
        statement = (
            select(Fragrance)
            .join(UserCollectionItem, UserCollectionItem.fragrance_id == Fragrance.id)
            .where(UserCollectionItem.user_id == user_id, UserCollectionItem.status == "owned")
            .options(*_discovery_options())
            .order_by(Fragrance.id)
        )
        return list(self._session.scalars(statement).unique())

    def candidates(
        self,
        user_id: UUID,
        *,
        gender: str | None = None,
        family: str | None = None,
        season: str | None = None,
        accord: str | None = None,
        minimum_value: float | None = None,
    ) -> list[Fragrance]:
        owned_ids = select(UserCollectionItem.fragrance_id).where(
            UserCollectionItem.user_id == user_id,
            UserCollectionItem.status == "owned",
        )
        owned_id_set = set(self._session.scalars(owned_ids))
        return FragranceRepository(self._session).search(
            user_id,
            limit=DISCOVERY_CANDIDATE_POOL,
            gender=gender,
            family=family,
            season=season,
            accord=accord,
            sort="popular",
            exclude_ids=owned_id_set,
            shared_only=True,
            minimum_value=minimum_value,
            _max_limit=DISCOVERY_CANDIDATE_POOL,
            _options=_discovery_options(),
        )

    def similarity_strengths(
        self, candidate_ids: set[UUID], owned_ids: set[UUID]
    ) -> dict[tuple[UUID, UUID], float]:
        if not candidate_ids or not owned_ids:
            return {}
        statement = select(FragranceSimilarity).where(
            or_(
                FragranceSimilarity.fragrance_id.in_(candidate_ids)
                & FragranceSimilarity.similar_fragrance_id.in_(owned_ids),
                FragranceSimilarity.fragrance_id.in_(owned_ids)
                & FragranceSimilarity.similar_fragrance_id.in_(candidate_ids),
            )
        )
        result: dict[tuple[UUID, UUID], float] = {}
        for link in self._session.scalars(statement):
            net = max((link.up_votes or 0) - (link.down_votes or 0), 0)
            strength = min(net / 100.0, 1.0) if link.kind == "reminds_me_of" else 0.25
            key = (link.fragrance_id, link.similar_fragrance_id)
            result[key] = max(result.get(key, 0.0), strength)
            result[(key[1], key[0])] = result[key]
        return result
