"""Private feedback linked to a caller-owned wear log."""

from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from scentiq_api.errors import not_found
from scentiq_api.models import WearFeedback, WearLog
from scentiq_api.schemas.wear import WearFeedbackRequest, WearFeedbackResponse


class WearFeedbackService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _owned(self, user_id: UUID, wear_id: UUID) -> None:
        wear = self.session.scalar(
            select(WearLog).where(WearLog.id == wear_id, WearLog.user_id == user_id)
        )
        if wear is None:
            raise not_found("Wear log not found")

    def get(self, user_id: UUID, wear_id: UUID) -> WearFeedbackResponse | None:
        self._owned(user_id, wear_id)
        row = self.session.scalar(
            select(WearFeedback).where(
                WearFeedback.wear_log_id == wear_id, WearFeedback.user_id == user_id
            )
        )
        if row is None:
            return None
        return WearFeedbackResponse(
            id=row.id,
            wear_log_id=wear_id,
            rating=row.rating,
            longevity=float(row.longevity) if row.longevity is not None else None,
            projection=row.projection,
            comments=row.comments,
        )

    def put(
        self, user_id: UUID, wear_id: UUID, request: WearFeedbackRequest
    ) -> WearFeedbackResponse:
        self._owned(user_id, wear_id)
        row = self.session.scalar(
            select(WearFeedback).where(
                WearFeedback.wear_log_id == wear_id, WearFeedback.user_id == user_id
            )
        )
        if row is None:
            row = WearFeedback(user_id=user_id, wear_log_id=wear_id)
            self.session.add(row)
        row.rating = request.rating
        row.longevity = Decimal(str(request.longevity)) if request.longevity is not None else None
        row.projection = request.projection
        row.comments = request.comments
        self.session.flush()
        result = self.get(user_id, wear_id)
        assert result is not None
        return result
