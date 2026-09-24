"""Profile, preference and account-deletion endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from scentiq_api.auth import AuthenticatedUser, CurrentUserDependency
from scentiq_api.repositories import IdentityRepository, UserRepository
from scentiq_api.schemas import (
    DeletionResponse,
    MeResponse,
    MeUpdateRequest,
    PreferencesResponse,
    PreferencesUpdateRequest,
)
from scentiq_api.services import AccountDeletionService, ProfileService


def create_me_router(
    get_session: object,
    current_user: CurrentUserDependency,
    *,
    current_user_allowing_pending: CurrentUserDependency,
) -> APIRouter:
    router = APIRouter(prefix="/me", tags=["me"])

    @router.get("", response_model=MeResponse)
    def get_me(
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user)],
    ) -> MeResponse:
        return ProfileService(UserRepository(session)).get(user.user_id)

    @router.patch("", response_model=MeResponse)
    def update_me(
        payload: MeUpdateRequest,
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user)],
    ) -> MeResponse:
        updated = ProfileService(UserRepository(session)).update(user.user_id, payload)
        session.commit()
        return updated

    @router.patch("/preferences", response_model=PreferencesResponse)
    def update_preferences(
        payload: PreferencesUpdateRequest,
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user)],
    ) -> PreferencesResponse:
        updated = ProfileService(UserRepository(session)).replace_preferences(
            user.user_id,
            payload,
        )
        session.commit()
        return updated

    @router.post(
        "/deletion",
        response_model=DeletionResponse,
        status_code=status.HTTP_202_ACCEPTED,
    )
    def request_deletion(
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user)],
    ) -> DeletionResponse:
        """Phase one: mark the account pending.

        The caller deletes the provider identity next; the provider's signed
        webhook then drives the actual data removal.
        """
        service = AccountDeletionService(UserRepository(session), IdentityRepository(session))
        accepted = service.request_deletion(user.user_id)
        session.commit()
        return accepted

    @router.post("/deletion/cancel", status_code=status.HTTP_204_NO_CONTENT)
    def cancel_deletion(
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user_allowing_pending)],
    ) -> None:
        """Roll back the pending mark when the provider deletion call failed."""
        service = AccountDeletionService(UserRepository(session), IdentityRepository(session))
        service.cancel_deletion(user.user_id)
        session.commit()

    return router
