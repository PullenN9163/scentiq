"""Catalog access.

Every query is scoped to a caller: shared curated rows (NULL owner) are visible
to everyone, custom rows only to the user who created them. There is no method
here that can read another user's private entry.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import ColumnElement, Select, desc, func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy.sql.base import ExecutableOption

from scentiq_api.catalog_import.normalize import fold
from scentiq_api.models import (
    Accord,
    Brand,
    Fragrance,
    FragranceAccord,
    FragranceCommunityStats,
    FragranceNote,
    FragrancePerfumer,
    FragranceSimilarity,
)

MAX_SEARCH_LIMIT = 50


def _catalog_options() -> tuple[ExecutableOption, ...]:
    return (
        joinedload(Fragrance.brand),
        selectinload(Fragrance.note_links).joinedload(FragranceNote.note),
        selectinload(Fragrance.accord_links).joinedload(FragranceAccord.accord),
        selectinload(Fragrance.seasons),
        selectinload(Fragrance.occasions),
        selectinload(Fragrance.perfumer_links).joinedload(FragrancePerfumer.perfumer),
        selectinload(Fragrance.community),
        selectinload(Fragrance.source_links),
    )


def _visible_to(user_id: UUID) -> ColumnElement[bool]:
    return or_(Fragrance.owner_user_id.is_(None), Fragrance.owner_user_id == user_id)


class FragranceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def _base_query(self, user_id: UUID) -> Select[tuple[Fragrance]]:
        return (
            select(Fragrance)
            .join(Fragrance.brand)
            .where(_visible_to(user_id))
            .options(*_catalog_options())
        )

    def search(
        self,
        user_id: UUID,
        *,
        query: str | None = None,
        limit: int | None = 25,
        offset: int = 0,
        gender: str | None = None,
        family: str | None = None,
        season: str | None = None,
        accord: str | None = None,
        sort: str = "relevance",
        exclude_ids: set[UUID] | None = None,
        shared_only: bool = False,
        minimum_value: float | None = None,
        _max_limit: int = MAX_SEARCH_LIMIT,
    ) -> list[Fragrance]:
        statement = self._base_query(user_id)
        if shared_only:
            statement = statement.where(Fragrance.owner_user_id.is_(None))
        if exclude_ids:
            statement = statement.where(Fragrance.id.not_in(exclude_ids))
        if query:
            folded_query = fold(query)
            statement = statement.where(Fragrance.search_text.ilike(f"%{folded_query}%"))
        if gender:
            statement = statement.where(Fragrance.gender == gender)
        if family:
            statement = statement.where(func.lower(Fragrance.olfactory_family) == family.lower())
        if season:
            statement = statement.where(Fragrance.seasons.any(season=season))
        if accord:
            statement = statement.where(
                Fragrance.accord_links.any(
                    FragranceAccord.accord.has(func.lower(Accord.name) == accord.lower())
                )
            )
        if minimum_value is not None:
            statement = statement.where(
                Fragrance.community.has(
                    FragranceCommunityStats.price_value_average >= minimum_value
                )
            )

        dialect = self._session.get_bind().dialect.name
        if sort == "relevance" and query and dialect == "postgresql":
            statement = statement.order_by(
                desc(func.similarity(Fragrance.search_text, fold(query))),
                desc(Fragrance.popularity_score).nullslast(),
                Brand.name,
                Fragrance.name,
            )
        elif sort == "rating":
            statement = statement.order_by(
                desc(Fragrance.rating_average).nullslast(),
                desc(Fragrance.rating_count).nullslast(),
                Brand.name,
                Fragrance.name,
            )
        elif sort == "name":
            statement = statement.order_by(Brand.name, Fragrance.name)
        else:
            statement = statement.order_by(
                desc(Fragrance.popularity_score).nullslast(), Brand.name, Fragrance.name
            )
        if limit is not None:
            statement = statement.offset(max(offset, 0)).limit(min(max(limit, 1), _max_limit))
        return list(self._session.scalars(statement))

    def get(self, user_id: UUID, fragrance_id: UUID) -> Fragrance | None:
        statement = (
            select(Fragrance)
            .where(Fragrance.id == fragrance_id, _visible_to(user_id))
            .options(*_catalog_options())
        )
        return self._session.scalar(statement)

    def similar(self, user_id: UUID, fragrance_id: UUID, *, limit: int = 8) -> list[Fragrance]:
        net_votes = func.coalesce(FragranceSimilarity.up_votes, 0) - func.coalesce(
            FragranceSimilarity.down_votes, 0
        )
        statement = (
            select(Fragrance)
            .join(
                FragranceSimilarity,
                FragranceSimilarity.similar_fragrance_id == Fragrance.id,
            )
            .where(
                FragranceSimilarity.fragrance_id == fragrance_id,
                FragranceSimilarity.kind == "reminds_me_of",
                _visible_to(user_id),
            )
            .options(*_catalog_options())
            .order_by(desc(net_votes), FragranceSimilarity.rank, Fragrance.id)
            .limit(min(max(limit, 1), 8))
        )
        return list(self._session.scalars(statement))

    def find_custom_duplicate(
        self,
        user_id: UUID,
        *,
        brand_name: str,
        name: str,
        concentration: str,
    ) -> Fragrance | None:
        """Existing private entry matching a would-be new one, case-insensitively."""
        statement = (
            select(Fragrance)
            .join(Fragrance.brand)
            .where(
                Fragrance.owner_user_id == user_id,
                func.lower(Brand.name) == brand_name.lower(),
                func.lower(Fragrance.name) == name.lower(),
                func.lower(Fragrance.concentration) == concentration.lower(),
            )
            .options(joinedload(Fragrance.brand))
        )
        return self._session.scalar(statement)

    def find_or_create_custom_brand(self, user_id: UUID, brand_name: str) -> Brand:
        """Reuse a shared brand when the name matches, else the user's own brand.

        Matching a curated brand keeps a user's custom fragrance attached to the
        real house instead of creating a private duplicate of it.
        """
        shared = self._session.scalar(
            select(Brand).where(
                Brand.owner_user_id.is_(None),
                func.lower(Brand.name) == brand_name.lower(),
            )
        )
        if shared is not None:
            return shared

        owned = self._session.scalar(
            select(Brand).where(
                Brand.owner_user_id == user_id,
                func.lower(Brand.name) == brand_name.lower(),
            )
        )
        if owned is not None:
            return owned

        brand = Brand(
            name=brand_name,
            slug=_slugify(brand_name),
            owner_user_id=user_id,
        )
        self._session.add(brand)
        self._session.flush()
        return brand

    def add_custom(self, fragrance: Fragrance) -> Fragrance:
        self._session.add(fragrance)
        self._session.flush()
        return fragrance


def _slugify(value: str) -> str:
    cleaned = [character.lower() if character.isalnum() else "-" for character in value.strip()]
    slug = "".join(cleaned)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")[:120] or "brand"
