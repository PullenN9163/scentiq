from __future__ import annotations

from uuid import UUID

from sqlalchemy import distinct, func, or_, select
from sqlalchemy.orm import Session, joinedload, load_only, selectinload
from sqlalchemy.sql.base import ExecutableOption

from scentiq_api.models import (
    Accord,
    Fragrance,
    FragranceAccord,
    FragranceCommunityStats,
    FragranceNote,
    FragranceSeason,
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
        selectinload(Fragrance.seasons),
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

    def price_values(self, fragrance_ids: set[UUID]) -> dict[UUID, float]:
        """Community price-value averages, as the ``minimum_value`` filter reads them."""
        if not fragrance_ids:
            return {}
        statement = select(
            FragranceCommunityStats.fragrance_id, FragranceCommunityStats.price_value_average
        ).where(
            FragranceCommunityStats.fragrance_id.in_(fragrance_ids),
            FragranceCommunityStats.price_value_average.is_not(None),
        )
        return {
            fragrance_id: float(value) for fragrance_id, value in self._session.execute(statement)
        }

    def catalog_facets(self, user_id: UUID) -> dict[str, dict[str, int]]:
        """Fragrance counts per filter value over the whole eligible catalog.

        Eligible means shared and not owned by the member, i.e. the set the discovery
        candidate query draws its most popular rows from. Keys match the filter
        semantics of ``FragranceRepository.search``: gender exactly, family and accord
        name case-insensitively, season by presence of a season row.
        """
        owned_ids = set(
            self._session.scalars(
                select(UserCollectionItem.fragrance_id).where(
                    UserCollectionItem.user_id == user_id,
                    UserCollectionItem.status == "owned",
                )
            )
        )
        eligible = [Fragrance.owner_user_id.is_(None)]
        if owned_ids:
            eligible.append(Fragrance.id.not_in(owned_ids))

        family = func.lower(Fragrance.olfactory_family)
        accord_name = func.lower(Accord.name)
        statements = {
            "gender": select(Fragrance.gender, func.count(Fragrance.id))
            .where(*eligible, Fragrance.gender.is_not(None))
            .group_by(Fragrance.gender),
            "family": select(family, func.count(Fragrance.id))
            .where(*eligible, Fragrance.olfactory_family.is_not(None))
            .group_by(family),
            "season": select(FragranceSeason.season, func.count(distinct(Fragrance.id)))
            .select_from(Fragrance)
            .join(FragranceSeason, FragranceSeason.fragrance_id == Fragrance.id)
            .where(*eligible)
            .group_by(FragranceSeason.season),
            "accord": select(accord_name, func.count(distinct(Fragrance.id)))
            .select_from(Fragrance)
            .join(FragranceAccord, FragranceAccord.fragrance_id == Fragrance.id)
            .join(Accord, Accord.id == FragranceAccord.accord_id)
            .where(*eligible)
            .group_by(accord_name),
        }
        return {
            kind: {str(key): int(count) for key, count in self._session.execute(statement)}
            for kind, statement in statements.items()
        }

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
