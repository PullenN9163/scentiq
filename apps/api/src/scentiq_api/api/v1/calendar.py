"""Calendar connection and event endpoints."""

from collections.abc import Mapping
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from scentiq_api.auth import AuthenticatedUser, CurrentUserDependency
from scentiq_api.integrations.calendar import CalendarProvider
from scentiq_api.integrations.crypto import TokenCipher
from scentiq_api.repositories import CalendarRepository
from scentiq_api.schemas import (
    AuthorizationResponse,
    CalendarConnectionResponse,
    CalendarEventResponse,
    CalendarEventUpdateRequest,
    CalendarProviderStatus,
    CalendarSourceUpdateRequest,
    OAuthCallbackRequest,
)
from scentiq_api.schemas.calendar import CalendarProviderValue
from scentiq_api.services import CalendarService


def create_calendar_router(
    get_session: object,
    current_user: CurrentUserDependency,
    providers: Mapping[str, CalendarProvider],
    cipher: TokenCipher | None,
    public_app_url: str | None,
) -> APIRouter:
    router = APIRouter(prefix="/calendar", tags=["calendar"])

    def _service(session: Session) -> CalendarService:
        return CalendarService(CalendarRepository(session), providers, cipher, public_app_url)

    @router.get("/providers", response_model=list[CalendarProviderStatus])
    def list_providers(
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user)],
    ) -> list[CalendarProviderStatus]:
        return _service(session).provider_statuses()

    @router.get("/connections", response_model=list[CalendarConnectionResponse])
    def list_connections(
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user)],
    ) -> list[CalendarConnectionResponse]:
        return _service(session).list_connections(user.user_id)

    @router.post(
        "/connections/{provider}/authorize",
        response_model=AuthorizationResponse,
    )
    def authorize(
        provider: CalendarProviderValue,
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user)],
    ) -> AuthorizationResponse:
        """Begin a connection: returns the provider consent URL to redirect to."""
        url = _service(session).start_authorization(user.user_id, provider)
        session.commit()
        return AuthorizationResponse(authorization_url=url)

    @router.post(
        "/connections/{provider}/callback",
        response_model=CalendarConnectionResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def callback(
        provider: CalendarProviderValue,
        payload: OAuthCallbackRequest,
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user)],
    ) -> CalendarConnectionResponse:
        """Finish a connection with the code and state the provider returned.

        The state is spent and committed before the code is exchanged, so it
        cannot be replayed even if the exchange fails.
        """
        service = _service(session)
        verifier = service.consume_state(user.user_id, provider, payload.state)
        session.commit()
        connection = service.complete_authorization(user.user_id, provider, payload.code, verifier)
        session.commit()
        return connection

    @router.patch(
        "/connections/{connection_id}/sources/{source_id}",
        response_model=CalendarConnectionResponse,
    )
    def update_source(
        connection_id: UUID,
        source_id: UUID,
        payload: CalendarSourceUpdateRequest,
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user)],
    ) -> CalendarConnectionResponse:
        updated = _service(session).set_source_selected(
            user.user_id, connection_id, source_id, payload.is_selected
        )
        session.commit()
        return updated

    @router.post("/connections/{connection_id}/sync", response_model=CalendarConnectionResponse)
    def sync(
        connection_id: UUID,
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user)],
    ) -> CalendarConnectionResponse:
        synced = _service(session).sync_now(user.user_id, connection_id)
        session.commit()
        return synced

    @router.delete("/connections/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
    def disconnect(
        connection_id: UUID,
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user)],
    ) -> None:
        """Revoke the grant (best effort) and delete it with its calendars and events."""
        _service(session).disconnect(user.user_id, connection_id)
        session.commit()

    @router.get("/events", response_model=list[CalendarEventResponse])
    def list_events(
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user)],
        start: Annotated[datetime, Query(description="Inclusive, with an offset.")],
        end: Annotated[datetime, Query(description="Exclusive, at most 31 days after start.")],
        include_hidden: bool = False,
    ) -> list[CalendarEventResponse]:
        """Events overlapping the range from selected calendars.

        Connections not synced in the last 15 minutes are refreshed first.
        """
        events = _service(session).events(user.user_id, start, end, include_hidden=include_hidden)
        session.commit()
        return events

    @router.patch("/events/{event_id}", response_model=CalendarEventResponse)
    def update_event(
        event_id: UUID,
        payload: CalendarEventUpdateRequest,
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user)],
    ) -> CalendarEventResponse:
        updated = _service(session).set_event_hidden(user.user_id, event_id, payload.is_hidden)
        session.commit()
        return updated

    return router
