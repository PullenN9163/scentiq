from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from scentiq_api.models import Fragrance, UserCollectionItem


class CollectionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_user(self, user_id: UUID) -> list[UserCollectionItem]:
        statement = (
            select(UserCollectionItem)
            .where(UserCollectionItem.user_id == user_id)
            .join(UserCollectionItem.fragrance)
            .options(
                joinedload(UserCollectionItem.fragrance).joinedload(Fragrance.brand),
            )
            .order_by(Fragrance.name)
        )
        return list(self._session.scalars(statement))
