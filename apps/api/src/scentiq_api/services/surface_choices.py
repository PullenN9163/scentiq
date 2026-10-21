"""Persisted, non-repeating choice batches shared by discovery and layering."""

import hashlib
import json
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from scentiq_api.errors import conflict, not_found, unprocessable
from scentiq_api.models import CatalogImportRun, Fragrance, User, UserCollectionItem, UserPreference
from scentiq_api.models.surface_choices import SurfaceChoiceBatch, SurfaceChoiceReceipt
from scentiq_api.repositories import DiscoveryRepository, LayeringRepository
from scentiq_api.schemas.discovery import DiscoveryResult
from scentiq_api.schemas.layering import LayeringStackSuggestion
from scentiq_api.schemas.surface_choices import (
    DiscoveryChoiceParameters,
    LayeringChoiceParameters,
    SurfaceChoiceRequest,
    SurfaceChoiceResponse,
)
from scentiq_api.services.ai_ranking import ranking_configuration_version
from scentiq_api.services.discovery import DiscoveryService
from scentiq_api.services.layering import LayeringService
from scentiq_api.services.personalized_ranking import surface_context
from scentiq_api.services.taste_profile import TasteProfileService


def candidate_key(candidate: DiscoveryResult | LayeringStackSuggestion) -> str:
    if isinstance(candidate, DiscoveryResult):
        return str(candidate.fragrance.id)
    return ":".join(sorted(str(item.fragrance.id) for item in candidate.items))


def fingerprint(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


class SurfaceChoiceService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def choose(
        self,
        user_id: UUID,
        surface: Literal["discovery", "layering"],
        request: SurfaceChoiceRequest,
    ) -> SurfaceChoiceResponse:
        try:
            parameters = (
                DiscoveryChoiceParameters if surface == "discovery" else LayeringChoiceParameters
            ).model_validate(request.parameters)
        except ValidationError as error:
            raise unprocessable("invalid_parameters", "Check the recommendation filters") from error
        # A member lock serializes first-batch creation and every subsequent advance.
        user = self.session.scalar(select(User).where(User.id == user_id).with_for_update())
        if user is None:
            raise not_found("Member not found")
        profile = TasteProfileService(self.session).for_user(user_id)
        collection_state = list(
            self.session.execute(
                select(
                    UserCollectionItem.id,
                    UserCollectionItem.fragrance_id,
                    UserCollectionItem.status,
                    UserCollectionItem.updated_at,
                )
                .where(UserCollectionItem.user_id == user_id)
                .order_by(UserCollectionItem.id)
            )
        )
        preferences = self.session.get(UserPreference, user_id)
        latest_import = self.session.scalar(
            select(func.max(CatalogImportRun.finished_at)).where(
                CatalogImportRun.status == "succeeded"
            )
        )
        custom_versions = list(
            self.session.execute(
                select(Fragrance.id, Fragrance.updated_at)
                .where(Fragrance.owner_user_id == user_id)
                .order_by(Fragrance.id)
            )
        )
        batch_fingerprint = fingerprint(
            {
                "parameters": parameters.model_dump(mode="json"),
                "profile": profile.version,
                "algorithm": "surface-v1",
                "context": surface_context(self.session, user_id, profile),
                "ranking_configuration": ranking_configuration_version(surface),
                "catalog_import": latest_import,
                "custom_versions": [list(row) for row in custom_versions],
                "collection": [list(row) for row in collection_state],
                "preferences_updated_at": preferences.updated_at if preferences else None,
                "day": datetime.now(UTC).date(),
            }
        )
        batch = self.session.scalar(
            select(SurfaceChoiceBatch).where(
                SurfaceChoiceBatch.user_id == user_id,
                SurfaceChoiceBatch.surface == surface,
                SurfaceChoiceBatch.fingerprint == batch_fingerprint,
            )
        )
        if request.batch_id is not None and (batch is None or batch.id != request.batch_id):
            raise conflict(
                "batch_changed", "Your preferences or collection changed; refresh these options"
            )
        if batch is None:
            candidates: list[DiscoveryResult | LayeringStackSuggestion]
            if surface == "discovery":
                discovery = DiscoveryChoiceParameters.model_validate(request.parameters)
                candidates = list(
                    DiscoveryService(DiscoveryRepository(self.session)).discover(
                        user_id, limit=50, **discovery.model_dump(exclude_none=True)
                    )
                )
            else:
                layering = LayeringChoiceParameters.model_validate(request.parameters)
                candidates = list(
                    LayeringService(LayeringRepository(self.session)).stack_suggestions(
                        user_id, limit=50, **layering.model_dump(exclude_none=True)
                    )
                )
            distinct = {candidate_key(candidate): candidate for candidate in candidates}
            ordered = list(distinct.items())
            selected_key = ordered[0][0] if ordered else None
            batch = SurfaceChoiceBatch(
                user_id=user_id,
                surface=surface,
                fingerprint=batch_fingerprint,
                candidates=[candidate.model_dump(mode="json") for _, candidate in ordered],
                selected_key=selected_key,
                seen_keys=[selected_key] if selected_key else [],
            )
            self.session.add(batch)
            self.session.flush()
        request_fingerprint = fingerprint(request.model_dump(mode="json"))
        receipt = self.session.scalar(
            select(SurfaceChoiceReceipt).where(
                SurfaceChoiceReceipt.batch_id == batch.id,
                SurfaceChoiceReceipt.idempotency_key == request.idempotency_key,
            )
        )
        if receipt:
            if receipt.request_fingerprint != request_fingerprint:
                raise conflict("idempotency_conflict", "Use a new key for a different request")
            return SurfaceChoiceResponse.model_validate(receipt.response_data)
        candidate_type = DiscoveryResult if surface == "discovery" else LayeringStackSuggestion
        available = {
            candidate_key(candidate): candidate
            for item in batch.candidates
            for candidate in [candidate_type.model_validate(item)]
        }
        if request.reset:
            batch.seen_keys = []
        if request.reset or (
            request.advance and request.expected_candidate_id in {None, batch.selected_key}
        ):
            unseen = next((key for key in available if key not in batch.seen_keys), None)
            if unseen:
                batch.selected_key = unseen
                batch.seen_keys = [*batch.seen_keys, unseen]
        remaining = sum(key not in batch.seen_keys for key in available)
        result = SurfaceChoiceResponse(
            batch_id=batch.id,
            selected=available.get(batch.selected_key) if batch.selected_key else None,
            candidate_id=batch.selected_key,
            remaining_options=remaining,
            options_exhausted=remaining == 0,
        )
        self.session.add(
            SurfaceChoiceReceipt(
                batch_id=batch.id,
                idempotency_key=request.idempotency_key,
                request_fingerprint=request_fingerprint,
                response_data=result.model_dump(mode="json"),
            )
        )
        self.session.flush()
        return result
