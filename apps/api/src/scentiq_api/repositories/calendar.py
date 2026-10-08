"""Calendar connections, their calendars and synced events.

Every read takes the authenticated user id and filters on it, so another
member's connection, calendar or event is simply not found.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from uuid import UUID

from sqlalchemy import Row, delete, or_, select
from sqlalchemy.orm import Session

from scentiq_api.models import CalendarConnection, CalendarEvent, CalendarSource, OAuthState

MAX_EVENTS = 500

# The calendar name and provider are None for events not synced from a calendar.
EventRow = Row[tuple[CalendarEvent, str, str]]


class CalendarRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    # --- OAuth state -------------------------------------------------------

    def add_state(self, state: OAuthState) -> None:
        self._session.add(state)
        self._session.flush()

    def prune_states(self, now: datetime) -> None:
        self._session.execute(delete(OAuthState).where(OAuthState.expires_at < now))

    def take_state(self, user_id: UUID, provider: str, state_hash: str) -> OAuthState | None:
        """Remove and return the member's pending state, whatever its expiry."""
        state = self._session.scalar(
            select(OAuthState).where(
                OAuthState.state_hash == state_hash,
                OAuthState.user_id == user_id,
                OAuthState.provider == provider,
            )
        )
        if state is not None:
            self._session.delete(state)
            self._session.flush()
        return state

    # --- connections -------------------------------------------------------

    def list_connections(self, user_id: UUID) -> list[CalendarConnection]:
        return list(
            self._session.scalars(
                select(CalendarConnection)
                .where(CalendarConnection.user_id == user_id)
                .order_by(CalendarConnection.created_at, CalendarConnection.account_email)
            )
        )

    def get_connection(self, user_id: UUID, connection_id: UUID) -> CalendarConnection | None:
        return self._session.scalar(
            select(CalendarConnection).where(
                CalendarConnection.id == connection_id,
                CalendarConnection.user_id == user_id,
            )
        )

    def find_connection(
        self, user_id: UUID, provider: str, account_email: str
    ) -> CalendarConnection | None:
        return self._session.scalar(
            select(CalendarConnection).where(
                CalendarConnection.user_id == user_id,
                CalendarConnection.provider == provider,
                CalendarConnection.account_email == account_email,
            )
        )

    def lock_for_sync(self, connection_id: UUID) -> CalendarConnection | None:
        """The connection, locked for this transaction; None if another sync holds it.

        SQLite has no row locks, so there this is a plain read.
        """
        return self._session.scalar(
            select(CalendarConnection)
            .where(CalendarConnection.id == connection_id)
            .with_for_update(skip_locked=True)
            .execution_options(populate_existing=True)
        )

    def add_connection(self, connection: CalendarConnection) -> CalendarConnection:
        self._session.add(connection)
        self._session.flush()
        return connection

    def delete_connection(self, connection: CalendarConnection) -> None:
        # Calendars and their events go with it through ON DELETE CASCADE.
        self._session.execute(
            delete(CalendarConnection).where(CalendarConnection.id == connection.id)
        )
        self._session.flush()
        self._session.expunge(connection)

    def flush(self) -> None:
        self._session.flush()

    # --- calendars ---------------------------------------------------------

    def list_sources(self, connection_ids: Iterable[UUID]) -> list[CalendarSource]:
        identifiers = list(connection_ids)
        if not identifiers:
            return []
        return list(
            self._session.scalars(
                select(CalendarSource)
                .where(CalendarSource.connection_id.in_(identifiers))
                .order_by(CalendarSource.is_primary.desc(), CalendarSource.name)
            )
        )

    def get_source(
        self, user_id: UUID, connection_id: UUID, source_id: UUID
    ) -> CalendarSource | None:
        return self._session.scalar(
            select(CalendarSource).where(
                CalendarSource.id == source_id,
                CalendarSource.connection_id == connection_id,
                CalendarSource.user_id == user_id,
            )
        )

    def add_source(self, source: CalendarSource) -> CalendarSource:
        self._session.add(source)
        self._session.flush()
        return source

    def delete_sources(self, source_ids: Iterable[UUID]) -> None:
        identifiers = list(source_ids)
        if identifiers:
            self._session.execute(delete(CalendarSource).where(CalendarSource.id.in_(identifiers)))
            self._session.flush()

    # --- events ------------------------------------------------------------

    def events_for_source(
        self, source_id: UUID, window_start: datetime, window_end: datetime
    ) -> list[CalendarEvent]:
        return list(
            self._session.scalars(
                select(CalendarEvent).where(
                    CalendarEvent.source_id == source_id,
                    CalendarEvent.starts_at < window_end,
                    CalendarEvent.ends_at > window_start,
                )
            )
        )

    def find_event(self, source_id: UUID, provider_event_id: str) -> CalendarEvent | None:
        return self._session.scalar(
            select(CalendarEvent).where(
                CalendarEvent.source_id == source_id,
                CalendarEvent.provider_event_id == provider_event_id,
            )
        )

    def add_event(self, event: CalendarEvent) -> None:
        self._session.add(event)

    def delete_events(self, event_ids: Iterable[UUID]) -> None:
        identifiers = list(event_ids)
        if identifiers:
            self._session.execute(delete(CalendarEvent).where(CalendarEvent.id.in_(identifiers)))

    def delete_source_events(self, source_id: UUID) -> None:
        self._session.execute(delete(CalendarEvent).where(CalendarEvent.source_id == source_id))
        self._session.flush()

    def get_event(self, user_id: UUID, event_id: UUID) -> CalendarEvent | None:
        return self._session.scalar(
            select(CalendarEvent).where(
                CalendarEvent.id == event_id, CalendarEvent.user_id == user_id
            )
        )

    def list_events(
        self,
        user_id: UUID,
        start: datetime,
        end: datetime,
        *,
        include_hidden: bool,
    ) -> list[EventRow]:
        """Events overlapping [start, end) from calendars the member has selected."""
        statement = (
            select(CalendarEvent, CalendarSource.name, CalendarConnection.provider)
            .outerjoin(CalendarSource, CalendarSource.id == CalendarEvent.source_id)
            .outerjoin(CalendarConnection, CalendarConnection.id == CalendarEvent.connection_id)
            .where(
                CalendarEvent.user_id == user_id,
                CalendarEvent.starts_at < end,
                CalendarEvent.ends_at > start,
                or_(CalendarEvent.source_id.is_(None), CalendarSource.is_selected.is_(True)),
            )
            .order_by(CalendarEvent.starts_at, CalendarEvent.title)
            .limit(MAX_EVENTS)
        )
        if not include_hidden:
            statement = statement.where(CalendarEvent.is_hidden.is_(False))
        return list(self._session.execute(statement).all())
