"""Calendar connections: the OAuth flow, on-demand sync and synced events.

Sync runs when events are read rather than on a schedule. A connection is
refreshed at most every `SYNC_INTERVAL`; concurrent readers skip a connection
another request is already syncing and serve what is stored.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from typing import get_args
from uuid import UUID

from scentiq_api.errors import ApiError, not_found, service_unavailable, unprocessable
from scentiq_api.integrations.calendar import (
    PROVIDERS,
    CalendarAuthError,
    CalendarProvider,
    CalendarProviderError,
    ProviderCalendar,
    ProviderEvent,
)
from scentiq_api.integrations.crypto import TokenCipher, TokenDecryptionError
from scentiq_api.models import CalendarConnection, CalendarEvent, CalendarSource, OAuthState
from scentiq_api.repositories import CalendarRepository
from scentiq_api.schemas import (
    CalendarConnectionResponse,
    CalendarEventResponse,
    CalendarProviderStatus,
    CalendarSourceResponse,
    Occasion,
)
from scentiq_api.services.event_classification import classify_event

STATE_TTL = timedelta(minutes=10)
SYNC_INTERVAL = timedelta(minutes=15)
# The synced window: recent enough for "today", far enough ahead for planning.
SYNC_PAST = timedelta(days=1)
SYNC_AHEAD = timedelta(days=21)
MAX_EVENT_RANGE = timedelta(days=31)
_OCCASIONS = frozenset(get_args(Occasion))


def provider_unavailable() -> ApiError:
    return service_unavailable(
        "calendar_provider_unavailable", "That calendar service is unavailable right now"
    )


def _hash_state(state: str) -> str:
    return hashlib.sha256(state.encode()).hexdigest()


def _code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def _token_context(user_id: UUID, provider: str) -> str:
    return f"calendar:{user_id}:{provider}"


def _aware(value: datetime) -> datetime:
    """SQLite drops the offset on read; every stored timestamp is UTC."""
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


class CalendarService:
    def __init__(
        self,
        repository: CalendarRepository,
        providers: Mapping[str, CalendarProvider],
        cipher: TokenCipher | None,
        public_app_url: str | None,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._repository = repository
        self._providers = providers
        self._cipher = cipher
        self._public_app_url = public_app_url
        self._clock = clock

    # --- providers ---------------------------------------------------------

    def provider_statuses(self) -> list[CalendarProviderStatus]:
        return [
            CalendarProviderStatus(provider=name, available=self._is_available(name))
            for name in PROVIDERS
        ]

    def _is_available(self, name: str) -> bool:
        return (
            name in self._providers
            and self._cipher is not None
            and self._public_app_url is not None
        )

    def _require_provider(self, name: str) -> tuple[CalendarProvider, TokenCipher, str]:
        if name not in PROVIDERS:
            raise not_found("Unknown calendar provider")
        provider = self._providers.get(name)
        if provider is None or self._cipher is None or self._public_app_url is None:
            raise service_unavailable(
                "calendar_provider_not_configured",
                "That calendar provider is not available here",
            )
        return (
            provider,
            self._cipher,
            f"{self._public_app_url}/integrations/calendar/{name}/callback",
        )

    # --- authorization -----------------------------------------------------

    def start_authorization(self, user_id: UUID, provider_name: str) -> str:
        provider, _, redirect_uri = self._require_provider(provider_name)
        now = self._clock()
        self._repository.prune_states(now)

        state = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        self._repository.add_state(
            OAuthState(
                state_hash=_hash_state(state),
                user_id=user_id,
                provider=provider_name,
                code_verifier=verifier,
                expires_at=now + STATE_TTL,
            )
        )
        return provider.authorization_url(
            state=state, code_challenge=_code_challenge(verifier), redirect_uri=redirect_uri
        )

    def consume_state(self, user_id: UUID, provider_name: str, state: str) -> str:
        """Spend the state and return its PKCE verifier.

        The caller commits this before exchanging the code, so a state can
        never be replayed even when the exchange fails.
        """
        self._require_provider(provider_name)
        pending = self._repository.take_state(user_id, provider_name, _hash_state(state))
        if pending is None or _aware(pending.expires_at) <= self._clock():
            raise unprocessable(
                "invalid_oauth_state",
                "That calendar connection request has expired. Start again from Settings.",
            )
        return pending.code_verifier

    def complete_authorization(
        self, user_id: UUID, provider_name: str, code: str, code_verifier: str
    ) -> CalendarConnectionResponse:
        provider, cipher, redirect_uri = self._require_provider(provider_name)
        try:
            tokens = provider.exchange_code(
                code=code, code_verifier=code_verifier, redirect_uri=redirect_uri
            )
            if tokens.scopes and not provider.required_scopes <= tokens.scopes:
                raise unprocessable(
                    "calendar_scope_not_granted",
                    "Calendar access was not granted. Connect again and allow calendar access.",
                )
            if tokens.refresh_token is None:
                raise unprocessable(
                    "authorization_failed", "The calendar provider did not grant offline access"
                )
            email = provider.account_email(tokens.access_token)
        except CalendarAuthError:
            raise unprocessable(
                "authorization_failed", "The calendar provider rejected the connection"
            ) from None
        except CalendarProviderError:
            raise provider_unavailable() from None

        sealed = cipher.encrypt(
            tokens.refresh_token, context=_token_context(user_id, provider_name)
        )
        connection = self._repository.find_connection(user_id, provider_name, email)
        if connection is None:
            connection = self._repository.add_connection(
                CalendarConnection(
                    user_id=user_id,
                    provider=provider_name,
                    account_email=email,
                    encrypted_refresh_token=sealed,
                    scopes=" ".join(sorted(tokens.scopes)),
                    status="active",
                )
            )
        else:
            # A reconnect: keep the member's calendar choices, replace the grant.
            connection.encrypted_refresh_token = sealed
            connection.scopes = " ".join(sorted(tokens.scopes))
            connection.status = "active"
            connection.last_error_code = None
            self._repository.flush()

        self._sync_with_access_token(connection, provider, tokens.access_token, self._clock())
        return self._connection_responses([connection])[0]

    # --- connections -------------------------------------------------------

    def list_connections(self, user_id: UUID) -> list[CalendarConnectionResponse]:
        return self._connection_responses(self._repository.list_connections(user_id))

    def _connection(self, user_id: UUID, connection_id: UUID) -> CalendarConnection:
        connection = self._repository.get_connection(user_id, connection_id)
        if connection is None:
            raise not_found("Calendar connection not found")
        return connection

    def set_source_selected(
        self, user_id: UUID, connection_id: UUID, source_id: UUID, selected: bool
    ) -> CalendarConnectionResponse:
        connection = self._connection(user_id, connection_id)
        source = self._repository.get_source(user_id, connection_id, source_id)
        if source is None:
            raise not_found("Calendar not found")
        if source.is_selected != selected:
            source.is_selected = selected
            if selected:
                # Fetch the newly included calendar on the next read.
                connection.last_attempted_at = None
            else:
                self._repository.delete_source_events(source.id)
            self._repository.flush()
        return self._connection_responses([connection])[0]

    def sync_now(self, user_id: UUID, connection_id: UUID) -> CalendarConnectionResponse:
        connection = self._connection(user_id, connection_id)
        locked = self._repository.lock_for_sync(connection.id)
        if locked is not None:
            self._sync(locked, self._clock())
        return self._connection_responses([connection])[0]

    def disconnect(self, user_id: UUID, connection_id: UUID) -> None:
        connection = self._connection(user_id, connection_id)
        provider = self._providers.get(connection.provider)
        if provider is not None and self._cipher is not None:
            try:
                refresh_token = self._cipher.decrypt(
                    connection.encrypted_refresh_token,
                    context=_token_context(user_id, connection.provider),
                )
            except TokenDecryptionError:
                pass
            else:
                # Best effort; the grant is removed here whatever the provider says.
                provider.revoke(refresh_token)
        self._repository.delete_connection(connection)

    # --- events ------------------------------------------------------------

    def events(
        self,
        user_id: UUID,
        start: datetime,
        end: datetime,
        *,
        include_hidden: bool = False,
    ) -> list[CalendarEventResponse]:
        if start.tzinfo is None or end.tzinfo is None:
            raise unprocessable("invalid_date_range", "start and end need a timezone offset")
        if end <= start:
            raise unprocessable("invalid_date_range", "end must be later than start")
        if end - start > MAX_EVENT_RANGE:
            raise unprocessable("invalid_date_range", "A range may span at most 31 days")

        self.sync_stale(user_id)
        rows = self._repository.list_events(user_id, start, end, include_hidden=include_hidden)
        return [
            _event_response(event, calendar_name, provider)
            for event, calendar_name, provider in rows
        ]

    def set_event_hidden(
        self, user_id: UUID, event_id: UUID, hidden: bool
    ) -> CalendarEventResponse:
        event = self._repository.get_event(user_id, event_id)
        if event is None:
            raise not_found("Event not found")
        event.is_hidden = hidden
        self._repository.flush()
        return _event_response(event, None, None)

    # --- sync --------------------------------------------------------------

    def sync_stale(self, user_id: UUID) -> None:
        now = self._clock()
        for connection in self._repository.list_connections(user_id):
            if connection.status != "active":
                continue
            attempted = connection.last_attempted_at
            if attempted is not None and now - _aware(attempted) < SYNC_INTERVAL:
                continue
            locked = self._repository.lock_for_sync(connection.id)
            if locked is None:
                continue
            self._sync(locked, now)

    def _sync(self, connection: CalendarConnection, now: datetime) -> None:
        connection.last_attempted_at = now
        provider = self._providers.get(connection.provider)
        if provider is None or self._cipher is None:
            connection.last_error_code = "provider_not_configured"
            self._repository.flush()
            return

        context = _token_context(connection.user_id, connection.provider)
        try:
            refresh_token = self._cipher.decrypt(
                connection.encrypted_refresh_token, context=context
            )
        except TokenDecryptionError:
            self._mark_reauth(connection, "token_unreadable")
            return

        try:
            tokens = provider.refresh(refresh_token)
        except CalendarAuthError:
            self._mark_reauth(connection, "reauth_required")
            return
        except CalendarProviderError as error:
            connection.last_error_code = error.code
            self._repository.flush()
            return

        # Providers may rotate the refresh token; the old one can stop working
        # at any moment, so the new one is stored in this same transaction.
        new_refresh_token = tokens.refresh_token or refresh_token
        if new_refresh_token != refresh_token or self._cipher.needs_rotation(
            connection.encrypted_refresh_token
        ):
            connection.encrypted_refresh_token = self._cipher.encrypt(
                new_refresh_token, context=context
            )

        self._sync_with_access_token(connection, provider, tokens.access_token, now)

    def _sync_with_access_token(
        self,
        connection: CalendarConnection,
        provider: CalendarProvider,
        access_token: str,
        now: datetime,
    ) -> None:
        connection.last_attempted_at = now
        window_start, window_end = now - SYNC_PAST, now + SYNC_AHEAD
        try:
            sources = self._reconcile_sources(connection, provider.list_calendars(access_token))
            for source in sources:
                if not source.is_selected:
                    continue
                try:
                    events = provider.list_events(
                        access_token, source.provider_calendar_id, window_start, window_end
                    )
                except CalendarProviderError as error:
                    if error.code == "calendar_not_found":
                        continue
                    raise
                self._replace_window(connection, source, events, window_start, window_end)
        except CalendarAuthError:
            self._mark_reauth(connection, "reauth_required")
            return
        except CalendarProviderError as error:
            connection.last_error_code = error.code
            self._repository.flush()
            return

        connection.status = "active"
        connection.last_error_code = None
        connection.last_synced_at = now
        self._repository.flush()

    def _reconcile_sources(
        self, connection: CalendarConnection, calendars: list[ProviderCalendar]
    ) -> list[CalendarSource]:
        existing = {
            source.provider_calendar_id: source
            for source in self._repository.list_sources([connection.id])
        }
        is_first_sync = not existing
        current: list[CalendarSource] = []
        for calendar in calendars:
            source = existing.pop(calendar.id, None)
            if source is None:
                source = self._repository.add_source(
                    CalendarSource(
                        connection_id=connection.id,
                        user_id=connection.user_id,
                        provider_calendar_id=calendar.id,
                        name=calendar.name,
                        color=calendar.color,
                        is_primary=calendar.is_primary,
                        # Only the main calendar starts included; shared and
                        # holiday calendars are opt-in.
                        is_selected=calendar.is_primary or (is_first_sync and len(calendars) == 1),
                    )
                )
            else:
                source.name = calendar.name
                source.color = calendar.color
                source.is_primary = calendar.is_primary
            current.append(source)
        # Calendars the account no longer has; their events cascade away.
        self._repository.delete_sources(source.id for source in existing.values())
        return current

    def _replace_window(
        self,
        connection: CalendarConnection,
        source: CalendarSource,
        events: list[ProviderEvent],
        window_start: datetime,
        window_end: datetime,
    ) -> None:
        stored = {
            event.provider_event_id: event
            for event in self._repository.events_for_source(source.id, window_start, window_end)
        }
        for incoming in events:
            classification = classify_event(incoming.title)
            event = stored.pop(incoming.id, None) or self._repository.find_event(
                source.id, incoming.id
            )
            if event is None:
                self._repository.add_event(
                    CalendarEvent(
                        user_id=connection.user_id,
                        connection_id=connection.id,
                        source_id=source.id,
                        provider_event_id=incoming.id,
                        title=incoming.title,
                        starts_at=incoming.starts_at,
                        ends_at=incoming.ends_at,
                        is_all_day=incoming.is_all_day,
                        location_label=incoming.location,
                        event_type=classification.occasion,
                        formality=classification.formality,
                        is_hidden=False,
                    )
                )
                continue
            # The member's choice to hide an event survives a re-sync.
            event.title = incoming.title
            event.starts_at = incoming.starts_at
            event.ends_at = incoming.ends_at
            event.is_all_day = incoming.is_all_day
            event.location_label = incoming.location
            event.event_type = classification.occasion
            event.formality = classification.formality
        # Anything left was cancelled, deleted or moved out of the window.
        self._repository.delete_events(event.id for event in stored.values())
        self._repository.flush()

    def _mark_reauth(self, connection: CalendarConnection, code: str) -> None:
        connection.status = "reauth_required"
        connection.last_error_code = code
        self._repository.flush()

    # --- responses ---------------------------------------------------------

    def _connection_responses(
        self, connections: list[CalendarConnection]
    ) -> list[CalendarConnectionResponse]:
        sources_by_connection: dict[UUID, list[CalendarSourceResponse]] = {}
        for source in self._repository.list_sources(connection.id for connection in connections):
            sources_by_connection.setdefault(source.connection_id, []).append(
                CalendarSourceResponse(
                    id=source.id,
                    name=source.name,
                    color=source.color,
                    is_primary=source.is_primary,
                    is_selected=source.is_selected,
                )
            )
        return [
            CalendarConnectionResponse(
                id=connection.id,
                provider="microsoft" if connection.provider == "microsoft" else "google",
                account_email=connection.account_email,
                status="reauth_required" if connection.status == "reauth_required" else "active",
                last_synced_at=(
                    _aware(connection.last_synced_at) if connection.last_synced_at else None
                ),
                last_error_code=connection.last_error_code,
                sources=sources_by_connection.get(connection.id, []),
            )
            for connection in connections
        ]


def _event_response(
    event: CalendarEvent, calendar_name: str | None, provider: str | None
) -> CalendarEventResponse:
    return CalendarEventResponse.model_validate(
        {
            "id": event.id,
            "title": event.title,
            "starts_at": _aware(event.starts_at),
            "ends_at": _aware(event.ends_at),
            "is_all_day": event.is_all_day,
            "location_label": event.location_label,
            "occasion": event.event_type if event.event_type in _OCCASIONS else "other",
            "formality": event.formality,
            "is_hidden": event.is_hidden,
            "calendar_name": calendar_name,
            "provider": provider,
        }
    )
