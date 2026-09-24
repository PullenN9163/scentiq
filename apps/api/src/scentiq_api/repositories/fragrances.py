"""Catalog access.

Every query is scoped to a caller: shared curated rows (NULL owner) are visible
to everyone, custom rows only to the user who created them. There is no method
here that can read another user's private entry.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import ColumnElement, Select, func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from scentiq_api.models import Brand, Fragrance, FragranceAccord, FragranceNote

MAX_SEARCH_LIMIT = 50


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
            .options(joinedload(Fragrance.brand))
        )

    def search(
        self,
        user_id: UUID,
        *,
        query: str | None = None,
        limit: int = 25,
    ) -> list[Fragrance]:
        statement = self._base_query(user_id)
        if query:
            # Case-insensitive contains on both fragrance and brand name.
            pattern = f"%{query.strip()}%"
            statement = statement.where(
                or_(Fragrance.name.ilike(pattern), Brand.name.ilike(pattern))
            )
        statement = statement.order_by(Brand.name, Fragrance.name).limit(
            min(max(limit, 1), MAX_SEARCH_LIMIT)
        )
        return list(self._session.scalars(statement))

    def get(self, user_id: UUID, fragrance_id: UUID) -> Fragrance | None:
        statement = (
            select(Fragrance)
            .where(Fragrance.id == fragrance_id, _visible_to(user_id))
            .options(
                joinedload(Fragrance.brand),
                selectinload(Fragrance.note_links).joinedload(FragranceNote.note),
                selectinload(Fragrance.accord_links).joinedload(FragranceAccord.accord),
                selectinload(Fragrance.seasons),
                selectinload(Fragrance.occasions),
            )
        )
        return self._session.scalar(statement)

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
