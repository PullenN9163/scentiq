"""Outlook calendars over Microsoft Graph, and which providers are configured."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from scentiq_api.api.v1 import configured_calendar_providers
from scentiq_api.config import Settings
from scentiq_api.integrations.calendar import (
    CalendarAuthError,
    CalendarProviderError,
    MicrosoftCalendarProvider,
)
from scentiq_api.integrations.calendar.microsoft import GRAPH_API

NOW = datetime(2026, 9, 26, 12, 0, tzinfo=UTC)


def _microsoft(handler: Any) -> MicrosoftCalendarProvider:
    return MicrosoftCalendarProvider(
        client_id="client-id",
        client_secret="client-secret",
        transport=httpx.MockTransport(handler),
    )


def test_authorization_url_requests_offline_calendar_access_for_any_account() -> None:
    url = _microsoft(lambda _: httpx.Response(500)).authorization_url(
        state="state", code_challenge="challenge", redirect_uri="https://app.test/cb"
    )
    parsed = urlparse(url)
    parameters = parse_qs(parsed.query)

    assert parsed.netloc == "login.microsoftonline.com"
    assert parsed.path == "/common/oauth2/v2.0/authorize"
    assert "offline_access" in parameters["scope"][0].split()
    assert "Calendars.Read" in parameters["scope"][0].split()
    assert parameters["code_challenge_method"] == ["S256"]
    assert "client_secret" not in parameters


@pytest.mark.parametrize(
    "granted",
    [
        "openid email offline_access User.Read Calendars.Read",
        "https://graph.microsoft.com/Calendars.Read https://graph.microsoft.com/User.Read",
    ],
)
def test_granted_scopes_are_normalised(granted: str) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200, json={"access_token": "a", "refresh_token": "r2", "scope": granted}
        )

    tokens = _microsoft(handler).refresh("r1")

    assert "calendars.read" in tokens.scopes
    assert tokens.refresh_token == "r2"
    form = parse_qs(seen[0].content.decode())
    assert form["grant_type"] == ["refresh_token"]
    assert "offline_access" in form["scope"][0]


@pytest.mark.parametrize("error", ["invalid_grant", "interaction_required"])
def test_an_unusable_grant_is_an_auth_error(error: str) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": error, "error_description": "AADSTS..."})

    with pytest.raises(CalendarAuthError):
        _microsoft(handler).refresh("r1")


@pytest.mark.parametrize(
    ("profile", "email"),
    [
        (
            {"mail": "Work@Contoso.com", "userPrincipalName": "w@contoso.onmicrosoft.com"},
            "work@contoso.com",
        ),
        ({"mail": None, "userPrincipalName": "Person@outlook.com"}, "person@outlook.com"),
    ],
)
def test_account_email_falls_back_to_the_sign_in_name(profile: dict[str, Any], email: str) -> None:
    assert _microsoft(lambda _: httpx.Response(200, json=profile)).account_email("a") == email


def test_account_without_an_address_is_refused() -> None:
    with pytest.raises(CalendarProviderError):
        _microsoft(lambda _: httpx.Response(200, json={"mail": None})).account_email("a")


def test_calendars_follow_next_links() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("$skip") == "1":
            return httpx.Response(200, json={"value": [{"id": "shared", "name": "Team"}]})
        return httpx.Response(
            200,
            json={
                "value": [
                    {
                        "id": "AAMk=",
                        "name": "Calendar",
                        "hexColor": "#0078d4",
                        "isDefaultCalendar": True,
                    }
                ],
                "@odata.nextLink": f"{GRAPH_API}/me/calendars?$skip=1",
            },
        )

    calendars = _microsoft(handler).list_calendars("a")

    assert [(item.id, item.name, item.is_primary, item.color) for item in calendars] == [
        ("AAMk=", "Calendar", True, "#0078d4"),
        ("shared", "Team", False, None),
    ]


def test_next_links_off_graph_are_not_followed() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(
            200, json={"value": [], "@odata.nextLink": "https://attacker.test/steal"}
        )

    _microsoft(handler).list_calendars("a")
    assert len(calls) == 1


def test_events_are_read_in_utc_and_filtered() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "value": [
                    {
                        "id": "timed",
                        "subject": "Client lunch",
                        "start": {"dateTime": "2026-09-26T12:30:00.0000000", "timeZone": "UTC"},
                        "end": {"dateTime": "2026-09-26T13:30:00.0000000", "timeZone": "UTC"},
                        "isAllDay": False,
                        "location": {"displayName": "Dishoom"},
                    },
                    {
                        "id": "all-day",
                        "subject": "Offsite",
                        "start": {"dateTime": "2026-09-28T00:00:00.0000000", "timeZone": "UTC"},
                        "end": {"dateTime": "2026-09-29T00:00:00.0000000", "timeZone": "UTC"},
                        "isAllDay": True,
                        "location": {"displayName": ""},
                    },
                    {"id": "cancelled", "isCancelled": True, "subject": "Old"},
                    {
                        "id": "private",
                        "start": {"dateTime": "2026-09-27T09:00:00.0000000"},
                        "end": {"dateTime": "2026-09-27T10:00:00.0000000"},
                    },
                ]
            },
        )

    events = _microsoft(handler).list_events("a", "AAMk/=", NOW, NOW + timedelta(days=7))

    request = seen[0]
    assert request.headers["Prefer"] == 'outlook.timezone="UTC"'
    assert request.url.raw_path.startswith(b"/v1.0/me/calendars/AAMk%2F%3D/calendarView")
    assert request.url.params["startDateTime"] == "2026-09-26T12:00:00Z"
    assert [event.id for event in events] == ["timed", "all-day", "private"]
    timed, all_day, private = events
    assert timed.starts_at == datetime(2026, 9, 26, 12, 30, tzinfo=UTC)
    assert timed.location == "Dishoom"
    assert all_day.is_all_day
    assert all_day.starts_at == datetime(2026, 9, 28, tzinfo=UTC)
    assert all_day.location is None
    assert private.title == "Busy"


def test_expired_access_is_an_auth_error() -> None:
    with pytest.raises(CalendarAuthError):
        _microsoft(lambda _: httpx.Response(401)).list_events("a", "c", NOW, NOW)


def test_revoke_makes_no_call() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise AssertionError("no revocation endpoint should be called")

    _microsoft(handler).revoke("r1")


def _settings(**values: Any) -> Settings:
    return Settings(
        SCENTIQ_ENV="test",
        DATABASE_URL="postgresql+psycopg://user:password@localhost/scentiq",
        CORS_ORIGINS="http://localhost:3000",
        **values,
    )


def test_only_fully_credentialed_providers_are_configured() -> None:
    assert configured_calendar_providers(_settings()) == {}
    assert configured_calendar_providers(_settings(GOOGLE_OAUTH_CLIENT_ID="id")) == {}

    providers = configured_calendar_providers(
        _settings(
            GOOGLE_OAUTH_CLIENT_ID="g-id",
            GOOGLE_OAUTH_CLIENT_SECRET="g-secret",
            MICROSOFT_OAUTH_CLIENT_ID="m-id",
            MICROSOFT_OAUTH_CLIENT_SECRET="m-secret",
        )
    )
    assert sorted(providers) == ["google", "microsoft"]
