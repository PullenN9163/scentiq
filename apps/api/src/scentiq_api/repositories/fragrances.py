from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from scentiq_api.models import Brand, Fragrance, FragranceAccord, FragranceNote


class FragranceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list(self) -> list[Fragrance]:
        statement = (
            select(Fragrance)
            .join(Fragrance.brand)
            .options(joinedload(Fragrance.brand))
            .order_by(Brand.name, Fragrance.name)
        )
        return list(self._session.scalars(statement))

    def get(self, fragrance_id: UUID) -> Fragrance | None:
        statement = (
            select(Fragrance)
            .where(Fragrance.id == fragrance_id)
            .options(
                joinedload(Fragrance.brand),
                selectinload(Fragrance.note_links).joinedload(FragranceNote.note),
                selectinload(Fragrance.accord_links).joinedload(FragranceAccord.accord),
                selectinload(Fragrance.seasons),
                selectinload(Fragrance.occasions),
            )
        )
        return self._session.scalar(statement)
