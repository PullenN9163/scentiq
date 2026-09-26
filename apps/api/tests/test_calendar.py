"""Calendar connections: token sealing, classification, Google parsing, the OAuth
flow, on-demand sync and member isolation."""

from __future__ import annotations

import base64
import os
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import httpx
import pytest
from domain_fixtures import make_user
from sqlalchemy import select
from sqlalchemy.orm import Session

from scentiq_api.errors import ApiError
from scentiq_api.integrations.calendar import (
    CalendarAuthError,
    CalendarProviderError,
    CalendarProviderName,
    GoogleCalendarProvider,
    ProviderCalendar,
    ProviderEvent,
    TokenSet,
)
from scentiq_api.integrations.calendar.google import CALENDAR_SCOPE
from scentiq_api.integrations.crypto import TokenCipher, TokenDecryptionError
from scentiq_api.models import CalendarConnection, CalendarEvent, CalendarSource, OAuthState
from scentiq_api.repositories import CalendarRepository, IdentityRepository
from scentiq_api.services import CalendarService
from scentiq_api.services.event_classification import classify_event

NOW = datetime(2026, 9, 26, 12, 0, tzinfo=UTC)
APP_URL = "https://app.test.invalid"
KEY = os.urandom(32)


# --- token sealing -------------------------------------------------------


def test_tokens_round_trip_and_are_not_stored_in_plaintext() -> None:
    cipher = TokenCipher([KEY])
    sealed = cipher.encrypt("refresh-secret", context="calendar:a:google")

    assert "refresh-secret" not in sealed
    assert cipher.decrypt(sealed, context="calendar:a:google") == "refresh-secret"
    # A fresh nonce every time.
    assert cipher.encrypt("refresh-secret", context="calendar:a:google") != sealed


def test_a_token_moved_to_another_member_does_not_decrypt() -> None:
    cipher = TokenCipher([KEY])
    sealed = cipher.encrypt("refresh-secret", context="calendar:a:google")

    with pytest.raises(TokenDecryptionError):
        cipher.decrypt(sealed, context="calendar:b:google")


def test_a_tampered_token_does_not_decrypt() -> None:
    cipher = TokenCipher([KEY])
    version, key_id, payload = cipher.encrypt("secret", context="c").split(":")
    raw = bytearray(base64.urlsafe_b64decode(payload))
    raw[-1] ^= 1
    tampered = f"{version}:{key_id}:{base64.urlsafe_b64encode(bytes(raw)).decode()}"

    with pytest.raises(TokenDecryptionError):
        cipher.decrypt(tampered, context="c")
    with pytest.raises(TokenDecryptionError):
        cipher.decrypt("not-a-token", context="c")


def test_rotated_keys_still_read_old_tokens() -> None:
    old_key, new_key = os.urandom(32), os.urandom(32)
    sealed_with_old = TokenCipher([old_key]).encrypt("secret", context="c")

    rotated = TokenCipher([new_key, old_key])

    assert rotated.decrypt(sealed_with_old, context="c") == "secret"
    assert rotated.needs_rotation(sealed_with_old)
    assert not rotated.needs_rotation(rotated.encrypt("secret", context="c"))
    with pytest.raises(TokenDecryptionError):
        TokenCipher([new_key]).decrypt(sealed_with_old, context="c")


# --- classification ------------------------------------------------------


@pytest.mark.parametrize(
    ("title", "occasion", "formality"),
    [
        ("Weekly team sync", "work", "smart"),
        ("1:1 with Priya", "work", "smart"),
        ("Client pitch", "work", "smart"),
        ("Team dinner", "dinner", "smart"),
        ("Sam's wedding drinks", "formal", "formal"),
        ("Date night", "date", "smart"),
        ("Update the roadmap", "other", None),
        ("Flight to Lisbon", "travel", "casual"),
        ("Yoga", "gym", "casual"),
        ("Birthday party", "party", "smart"),
        ("Coffee with Alex", "casual", "casual"),
        ("Dentist", "other", None),
    ],
)
def test_events_are_classified_from_their_title(
    title: str, occasion: str, formality: str | None
) -> None:
    classification = classify_event(title)
    assert classification.occasion == occasion
    assert classification.formality == formality


# --- Google client ---------------------------------------------------------


def _google(handler: Any) -> GoogleCalendarProvider:
    return GoogleCalendarProvider(
        client_id="client-id",
        client_secret="client-secret",
        transport=httpx.MockTransport(handler),
    )


def test_google_authorization_url_requests_offline_read_only_access() -> None:
    url = _google(lambda _: httpx.Response(500)).authorization_url(
        state="state-value", code_challenge="challenge", redirect_uri=f"{APP_URL}/cb"
    )
    parameters = parse_qs(urlparse(url).query)

    assert url.startswith("https://accounts.google.com/")
    assert parameters["scope"] == [f"openid email {CALENDAR_SCOPE}"]
    assert parameters["access_type"] == ["offline"]
    assert parameters["prompt"] == ["consent"]
    assert parameters["code_challenge_method"] == ["S256"]
    assert parameters["state"] == ["state-value"]
    assert "client_secret" not in parameters


def test_google_exchange_reads_tokens_and_scopes() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "access_token": "access",
                "refresh_token": "refresh",
                "scope": f"openid {CALENDAR_SCOPE}",
                "expires_in": 3599,
            },
        )

    tokens = _google(handler).exchange_code(
        code="code", code_verifier="verifier", redirect_uri=f"{APP_URL}/cb"
    )

    form = parse_qs(seen[0].content.decode())
    assert form["code_verifier"] == ["verifier"]
    assert form["grant_type"] == ["authorization_code"]
    assert tokens.refresh_token == "refresh"
    assert CALENDAR_SCOPE in tokens.scopes


def test_google_invalid_grant_is_an_auth_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": "invalid_grant"})

    with pytest.raises(CalendarAuthError):
        _google(handler).refresh("revoked")


def test_google_outage_is_a_provider_error_without_details() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    with pytest.raises(CalendarProviderError) as error:
        _google(handler).refresh("secret-refresh-token")
    assert error.value.code == "provider_unavailable"
    assert "secret-refresh-token" not in str(error.value)


def test_google_expired_access_token_is_an_auth_error() -> None:
    with pytest.raises(CalendarAuthError):
        _google(lambda _: httpx.Response(401)).list_calendars("expired")


def test_google_calendars_follow_pagination() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("pageToken") == "next":
            return httpx.Response(200, json={"items": [{"id": "team@group", "summary": "Team"}]})
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": "me@example.com",
                        "summary": "me@example.com",
                        "summaryOverride": "Personal",
                        "primary": True,
                        "backgroundColor": "#9fc6e7",
                    }
                ],
                "nextPageToken": "next",
            },
        )

    calendars = _google(handler).list_calendars("access")

    assert [(item.id, item.name, item.is_primary) for item in calendars] == [
        ("me@example.com", "Personal", True),
        ("team@group", "Team", False),
    ]


def test_google_events_are_parsed_and_filtered() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": "timed",
                        "summary": " Team sync ",
                        "location": "Room 4",
                        "start": {"dateTime": "2026-09-26T09:00:00-04:00"},
                        "end": {"dateTime": "2026-09-26T09:30:00-04:00"},
                        "description": "never stored",
                        "attendees": [{"email": "someone@example.com"}],
                    },
                    {
                        "id": "all-day",
                        "summary": "Offsite",
                        "start": {"date": "2026-09-27"},
                        "end": {"date": "2026-09-28"},
                    },
                    {"id": "private", "start": {"dateTime": "2026-09-26T12:00:00Z"}, "end": {}},
                    {"id": "gone", "status": "cancelled"},
                    {
                        "id": "wfh",
                        "eventType": "workingLocation",
                        "start": {"date": "2026-09-26"},
                        "end": {"date": "2026-09-27"},
                    },
                ]
            },
        )

    events = _google(handler).list_events(
        "access", "team#calendar@group", NOW, NOW + timedelta(days=1)
    )

    assert seen[0].url.raw_path.startswith(b"/calendar/v3/calendars/team%23calendar%40group/")
    assert seen[0].url.params["singleEvents"] == "true"
    assert seen[0].url.params["timeMin"] == "2026-09-26T12:00:00Z"
    assert [event.id for event in events] == ["timed", "all-day", "private"]
    timed, all_day, private = events
    assert timed.title == "Team sync"
    assert timed.starts_at == datetime(2026, 9, 26, 13, 0, tzinfo=UTC)
    assert timed.location == "Room 4"
    assert all_day.is_all_day
    assert all_day.starts_at == datetime(2026, 9, 27, tzinfo=UTC)
    assert all_day.ends_at == datetime(2026, 9, 28, tzinfo=UTC)
    assert private.title == "Busy"
    assert private.ends_at == private.starts_at


def test_google_revoke_failures_are_ignored() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    _google(handler).revoke("token")


# --- the service ---------------------------------------------------------


def _event(event_id: str, title: str, *, day: int = 0, hour: int = 9) -> ProviderEvent:
    starts_at = datetime(2026, 9, 26, hour, tzinfo=UTC) + timedelta(days=day)
    return ProviderEvent(
        id=event_id,
        title=title,
        starts_at=starts_at,
        ends_at=starts_at + timedelta(hours=1),
        is_all_day=False,
        location=None,
    )


class FakeGoogle:
    """A CalendarProvider whose account, calendars and events tests control."""

    name: CalendarProviderName = "google"
    required_scopes = frozenset({CALENDAR_SCOPE})

    def __init__(self) -> None:
        self.email = "Member@Example.com"
        self.scopes = frozenset({"openid", "email", CALENDAR_SCOPE})
        self.issue_refresh_token: str | None = "refresh-1"
        self.rotate_to: str | None = None
        self.calendars = [
            ProviderCalendar(id="primary", name="Personal", color="#9fc6e7", is_primary=True),
            ProviderCalendar(id="holidays", name="Holidays", color=None, is_primary=False),
        ]
        self.events: dict[str, list[ProviderEvent]] = {
            "primary": [_event("e1", "Team sync"), _event("e2", "Dinner at Nopi", hour=19)],
            "holidays": [_event("h1", "Bank holiday")],
        }
        self.fail: CalendarProviderError | None = None
        self.refresh_calls: list[str] = []
        self.revoked: list[str] = []
        self.exchanges: list[dict[str, str]] = []

    def authorization_url(self, *, state: str, code_challenge: str, redirect_uri: str) -> str:
        return f"https://consent.test/?state={state}&challenge={code_challenge}&redirect={redirect_uri}"

    def exchange_code(self, *, code: str, code_verifier: str, redirect_uri: str) -> TokenSet:
        self.exchanges.append(
            {"code": code, "code_verifier": code_verifier, "redirect_uri": redirect_uri}
        )
        if self.fail:
            raise self.fail
        return TokenSet(
            access_token="access", refresh_token=self.issue_refresh_token, scopes=self.scopes
        )

    def refresh(self, refresh_token: str) -> TokenSet:
        self.refresh_calls.append(refresh_token)
        if self.fail:
            raise self.fail
        return TokenSet(access_token="access", refresh_token=self.rotate_to, scopes=self.scopes)

    def account_email(self, access_token: str) -> str:
        return self.email.lower()

    def list_calendars(self, access_token: str) -> list[ProviderCalendar]:
        if self.fail:
            raise self.fail
        return list(self.calendars)

    def list_events(
        self, access_token: str, calendar_id: str, start: datetime, end: datetime
    ) -> list[ProviderEvent]:
        if self.fail:
            raise self.fail
        return list(self.events.get(calendar_id, []))

    def revoke(self, refresh_token: str) -> None:
        self.revoked.append(refresh_token)


class Clock:
    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> datetime:
        return self.now


def _service(
    session: Session,
    provider: FakeGoogle | None,
    clock: Clock | None = None,
    *,
    cipher: TokenCipher | None = None,
    app_url: str | None = APP_URL,
) -> CalendarService:
    return CalendarService(
        CalendarRepository(session),
        {"google": provider} if provider is not None else {},
        cipher or TokenCipher([KEY]),
        app_url,
        clock=clock or Clock(),
    )


def _state_from(url: str) -> str:
    return parse_qs(urlparse(url).query)["state"][0]


def _connect(session: Session, user_id: Any, provider: FakeGoogle, clock: Clock) -> Any:
    service = _service(session, provider, clock)
    state = _state_from(service.start_authorization(user_id, "google"))
    verifier = service.consume_state(user_id, "google", state)
    return service.complete_authorization(user_id, "google", "auth-code", verifier)


def _window() -> tuple[datetime, datetime]:
    return datetime(2026, 9, 26, tzinfo=UTC), datetime(2026, 10, 3, tzinfo=UTC)


def test_providers_report_available_only_when_fully_configured(session: Session) -> None:
    assert [status.available for status in _service(session, FakeGoogle()).provider_statuses()] == [
        True,
        False,
    ]
    assert not _service(session, FakeGoogle(), app_url=None).provider_statuses()[0].available
    assert not _service(session, None).provider_statuses()[0].available


def test_an_unconfigured_provider_cannot_start(session: Session) -> None:
    user = make_user(session, email="a@example.com")
    with pytest.raises(ApiError) as error:
        _service(session, None).start_authorization(user.id, "google")
    assert error.value.status_code == 503


def test_connecting_stores_a_sealed_grant_and_syncs_the_primary_calendar(
    session: Session,
) -> None:
    user = make_user(session, email="a@example.com")
    provider = FakeGoogle()

    connection = _connect(session, user.id, provider, Clock())

    assert (
        provider.exchanges[0]["redirect_uri"] == f"{APP_URL}/integrations/calendar/google/callback"
    )
    assert connection.account_email == "member@example.com"
    assert connection.status == "active"
    assert [(source.name, source.is_selected) for source in connection.sources] == [
        ("Personal", True),
        ("Holidays", False),
    ]
    stored = session.scalar(select(CalendarConnection))
    assert stored is not None
    assert "refresh-1" not in stored.encrypted_refresh_token
    assert session.scalar(select(OAuthState)) is None

    events = _service(session, provider).events(user.id, *_window())
    assert [(event.title, event.occasion) for event in events] == [
        ("Team sync", "work"),
        ("Dinner at Nopi", "dinner"),
    ]
    assert events[0].calendar_name == "Personal"
    assert events[0].provider == "google"


def test_the_pkce_verifier_matches_the_challenge(session: Session) -> None:
    import hashlib

    user = make_user(session, email="a@example.com")
    provider = FakeGoogle()
    service = _service(session, provider)
    url = service.start_authorization(user.id, "google")
    challenge = parse_qs(urlparse(url).query)["challenge"][0]

    verifier = service.consume_state(user.id, "google", _state_from(url))

    expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=")
    assert challenge == expected.decode()


@pytest.mark.parametrize("problem", ["unknown", "expired", "reused", "other_member"])
def test_bad_states_are_refused(session: Session, problem: str) -> None:
    owner = make_user(session, email="owner@example.com")
    other = make_user(session, email="other@example.com")
    clock = Clock()
    service = _service(session, FakeGoogle(), clock)
    state = _state_from(service.start_authorization(owner.id, "google"))

    caller = owner.id
    if problem == "unknown":
        state = "x" * 43
    elif problem == "expired":
        clock.now = NOW + timedelta(minutes=11)
    elif problem == "reused":
        service.consume_state(owner.id, "google", state)
    elif problem == "other_member":
        caller = other.id

    with pytest.raises(ApiError) as error:
        service.consume_state(caller, "google", state)
    assert error.value.code == "invalid_oauth_state"


def test_a_grant_without_calendar_access_is_refused(session: Session) -> None:
    user = make_user(session, email="a@example.com")
    provider = FakeGoogle()
    provider.scopes = frozenset({"openid", "email"})

    with pytest.raises(ApiError) as error:
        _connect(session, user.id, provider, Clock())

    assert error.value.code == "calendar_scope_not_granted"
    assert session.scalar(select(CalendarConnection)) is None


def test_a_grant_without_a_refresh_token_is_refused(session: Session) -> None:
    user = make_user(session, email="a@example.com")
    provider = FakeGoogle()
    provider.issue_refresh_token = None

    with pytest.raises(ApiError) as error:
        _connect(session, user.id, provider, Clock())
    assert error.value.code == "authorization_failed"


def test_a_rejected_code_is_refused(session: Session) -> None:
    user = make_user(session, email="a@example.com")
    provider = FakeGoogle()
    provider.fail = CalendarAuthError()

    with pytest.raises(ApiError) as error:
        _connect(session, user.id, provider, Clock())
    assert error.value.code == "authorization_failed"


def test_reconnecting_keeps_calendar_choices(session: Session) -> None:
    user = make_user(session, email="a@example.com")
    provider = FakeGoogle()
    clock = Clock()
    connection = _connect(session, user.id, provider, clock)
    holidays = next(source for source in connection.sources if source.name == "Holidays")
    _service(session, provider, clock).set_source_selected(
        user.id, connection.id, holidays.id, True
    )

    provider.issue_refresh_token = "refresh-2"
    again = _connect(session, user.id, provider, clock)

    assert again.id == connection.id
    assert all(source.is_selected for source in again.sources)
    assert session.query(CalendarConnection).count() == 1


def test_recent_syncs_are_not_repeated(session: Session) -> None:
    user = make_user(session, email="a@example.com")
    provider = FakeGoogle()
    clock = Clock()
    _connect(session, user.id, provider, clock)

    clock.now = NOW + timedelta(minutes=5)
    _service(session, provider, clock).events(user.id, *_window())
    assert provider.refresh_calls == []

    clock.now = NOW + timedelta(minutes=20)
    _service(session, provider, clock).events(user.id, *_window())
    assert provider.refresh_calls == ["refresh-1"]


def test_a_rotated_refresh_token_is_kept(session: Session) -> None:
    user = make_user(session, email="a@example.com")
    provider = FakeGoogle()
    clock = Clock()
    _connect(session, user.id, provider, clock)

    provider.rotate_to = "refresh-2"
    clock.now = NOW + timedelta(minutes=20)
    _service(session, provider, clock).events(user.id, *_window())
    provider.rotate_to = None
    clock.now = NOW + timedelta(minutes=40)
    _service(session, provider, clock).events(user.id, *_window())

    assert provider.refresh_calls == ["refresh-1", "refresh-2"]


def test_a_revoked_grant_asks_to_reconnect_and_keeps_cached_events(session: Session) -> None:
    user = make_user(session, email="a@example.com")
    provider = FakeGoogle()
    clock = Clock()
    _connect(session, user.id, provider, clock)

    provider.fail = CalendarAuthError()
    clock.now = NOW + timedelta(minutes=20)
    events = _service(session, provider, clock).events(user.id, *_window())

    assert len(events) == 2
    [connection] = _service(session, provider, clock).list_connections(user.id)
    assert connection.status == "reauth_required"

    # A connection that needs reconnecting is not retried on every read.
    clock.now = NOW + timedelta(hours=2)
    _service(session, provider, clock).events(user.id, *_window())
    assert len(provider.refresh_calls) == 1


def test_a_provider_outage_serves_cached_events(session: Session) -> None:
    user = make_user(session, email="a@example.com")
    provider = FakeGoogle()
    clock = Clock()
    _connect(session, user.id, provider, clock)

    provider.fail = CalendarProviderError("provider_unavailable")
    clock.now = NOW + timedelta(minutes=20)
    events = _service(session, provider, clock).events(user.id, *_window())

    assert len(events) == 2
    [connection] = _service(session, provider, clock).list_connections(user.id)
    assert connection.status == "active"
    assert connection.last_error_code == "provider_unavailable"


def test_resync_updates_moves_and_removes_events_but_keeps_hidden_choices(
    session: Session,
) -> None:
    user = make_user(session, email="a@example.com")
    provider = FakeGoogle()
    clock = Clock()
    _connect(session, user.id, provider, clock)
    service = _service(session, provider, clock)
    sync = next(
        event for event in service.events(user.id, *_window()) if event.title == "Team sync"
    )
    service.set_event_hidden(user.id, sync.id, True)

    provider.events["primary"] = [_event("e1", "Team sync (moved)", hour=10)]
    clock.now = NOW + timedelta(minutes=20)
    visible = _service(session, provider, clock).events(user.id, *_window())
    everything = _service(session, provider, clock).events(user.id, *_window(), include_hidden=True)

    assert visible == []
    assert [(event.title, event.is_hidden) for event in everything] == [("Team sync (moved)", True)]


def test_deselecting_a_calendar_drops_its_events_and_reselecting_fetches_them(
    session: Session,
) -> None:
    user = make_user(session, email="a@example.com")
    provider = FakeGoogle()
    clock = Clock()
    connection = _connect(session, user.id, provider, clock)
    personal = next(source for source in connection.sources if source.is_primary)
    service = _service(session, provider, clock)

    service.set_source_selected(user.id, connection.id, personal.id, False)
    assert service.events(user.id, *_window()) == []
    assert session.query(CalendarEvent).count() == 0

    service.set_source_selected(user.id, connection.id, personal.id, True)
    assert len(service.events(user.id, *_window())) == 2


def test_a_calendar_removed_at_the_provider_is_removed_here(session: Session) -> None:
    user = make_user(session, email="a@example.com")
    provider = FakeGoogle()
    clock = Clock()
    _connect(session, user.id, provider, clock)

    provider.calendars = provider.calendars[:1]
    clock.now = NOW + timedelta(minutes=20)
    _service(session, provider, clock).events(user.id, *_window())

    assert [source.name for source in session.scalars(select(CalendarSource))] == ["Personal"]


def test_sync_now_ignores_the_interval(session: Session) -> None:
    user = make_user(session, email="a@example.com")
    provider = FakeGoogle()
    clock = Clock()
    connection = _connect(session, user.id, provider, clock)

    _service(session, provider, clock).sync_now(user.id, connection.id)

    assert provider.refresh_calls == ["refresh-1"]


def test_disconnecting_revokes_and_removes_everything(session: Session) -> None:
    user = make_user(session, email="a@example.com")
    provider = FakeGoogle()
    clock = Clock()
    connection = _connect(session, user.id, provider, clock)

    _service(session, provider, clock).disconnect(user.id, connection.id)

    assert provider.revoked == ["refresh-1"]
    assert session.query(CalendarConnection).count() == 0
    assert session.query(CalendarSource).count() == 0
    assert session.query(CalendarEvent).count() == 0


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (datetime(2026, 9, 26, tzinfo=UTC), datetime(2026, 9, 25, tzinfo=UTC)),
        (datetime(2026, 9, 1, tzinfo=UTC), datetime(2026, 10, 5, tzinfo=UTC)),
        (datetime(2026, 9, 26), datetime(2026, 9, 27)),
    ],
)
def test_event_ranges_are_validated(session: Session, start: datetime, end: datetime) -> None:
    user = make_user(session, email="a@example.com")
    with pytest.raises(ApiError) as error:
        _service(session, FakeGoogle()).events(user.id, start, end)
    assert error.value.code == "invalid_date_range"


def test_calendar_data_is_private_to_each_member(session: Session) -> None:
    owner = make_user(session, email="owner@example.com")
    other = make_user(session, email="other@example.com")
    provider = FakeGoogle()
    clock = Clock()
    connection = _connect(session, owner.id, provider, clock)
    event = _service(session, provider, clock).events(owner.id, *_window())[0]
    service = _service(session, provider, clock)

    assert service.list_connections(other.id) == []
    assert service.events(other.id, *_window()) == []
    for attempt in (
        lambda: service.sync_now(other.id, connection.id),
        lambda: service.disconnect(other.id, connection.id),
        lambda: service.set_source_selected(
            other.id, connection.id, connection.sources[0].id, False
        ),
        lambda: service.set_event_hidden(other.id, event.id, True),
        lambda: service.set_source_selected(owner.id, connection.id, uuid4(), False),
    ):
        with pytest.raises(ApiError) as error:
            attempt()
        assert error.value.status_code == 404
    assert session.query(CalendarConnection).count() == 1


def test_deleting_a_member_removes_their_calendar_data(session: Session) -> None:
    user = make_user(session, email="a@example.com")
    provider = FakeGoogle()
    clock = Clock()
    _connect(session, user.id, provider, clock)
    _service(session, provider, clock).start_authorization(user.id, "google")

    IdentityRepository(session).purge_user(user.id)

    for model in (CalendarConnection, CalendarSource, CalendarEvent, OAuthState):
        assert session.query(model).count() == 0
