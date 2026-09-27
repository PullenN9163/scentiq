"""The calendar endpoints over HTTP against PostgreSQL, with a fake Google."""

from __future__ import annotations

import base64
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from alembic import command
from alembic.config import Config
from auth_harness import (
    AUDIENCE,
    AUTHORIZED_PARTY,
    ISSUER,
    SERVICE_TOKEN,
    auth_headers,
    resolver,
)
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from scentiq_api.config import Settings
from scentiq_api.integrations.calendar import (
    CalendarAuthError,
    CalendarProviderError,
    CalendarProviderName,
    ProviderCalendar,
    ProviderEvent,
    TokenSet,
)
from scentiq_api.integrations.calendar.google import CALENDAR_SCOPE
from scentiq_api.main import create_app

pytestmark = pytest.mark.integration

API_ROOT = Path(__file__).parents[2]
APP_URL = "https://app.test.invalid"


class FakeGoogle:
    name: CalendarProviderName = "google"
    required_scopes = frozenset({CALENDAR_SCOPE})

    def __init__(self) -> None:
        self.revoked = False
        now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
        self.events = [
            ProviderEvent(
                id="standup",
                title="Standup",
                starts_at=now + timedelta(hours=1),
                ends_at=now + timedelta(hours=2),
                is_all_day=False,
                location=None,
            ),
            ProviderEvent(
                id="dinner",
                title="Anniversary dinner",
                starts_at=now + timedelta(days=1, hours=3),
                ends_at=now + timedelta(days=1, hours=5),
                is_all_day=False,
                location="Nopi",
            ),
        ]
        self.fail_refresh = False

    def authorization_url(self, *, state: str, code_challenge: str, redirect_uri: str) -> str:
        return f"https://consent.test/?state={state}&redirect_uri={redirect_uri}"

    def exchange_code(self, *, code: str, code_verifier: str, redirect_uri: str) -> TokenSet:
        if code == "misconfigured":
            raise CalendarProviderError("invalid_client")
        if code != "good-code":
            raise CalendarAuthError()
        return TokenSet("access", "refresh", frozenset({"openid", CALENDAR_SCOPE}))

    def refresh(self, refresh_token: str) -> TokenSet:
        if self.fail_refresh:
            raise CalendarAuthError()
        return TokenSet("access", None, frozenset({CALENDAR_SCOPE}))

    def account_email(self, access_token: str) -> str:
        return "member@example.com"

    def list_calendars(self, access_token: str) -> list[ProviderCalendar]:
        return [ProviderCalendar(id="primary", name="Personal", color=None, is_primary=True)]

    def list_events(
        self, access_token: str, calendar_id: str, start: datetime, end: datetime
    ) -> list[ProviderEvent]:
        return list(self.events)

    def revoke(self, refresh_token: str) -> None:
        self.revoked = True


def _settings() -> Settings:
    return Settings(
        SCENTIQ_ENV="test",
        DATABASE_URL=os.environ["DATABASE_URL"],
        CORS_ORIGINS="http://localhost:5173",
        CLERK_ISSUER=ISSUER,
        CLERK_AUDIENCE=AUDIENCE,
        CLERK_AUTHORIZED_PARTIES=AUTHORIZED_PARTY,
        INTERNAL_SERVICE_TOKEN=SERVICE_TOKEN,
        PUBLIC_APP_URL=APP_URL,
        INTEGRATION_TOKEN_ENCRYPTION_KEY=base64.b64encode(os.urandom(32)).decode(),
    )


def _reset_database() -> None:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(API_ROOT / "migrations"))
    command.downgrade(config, "base")
    command.upgrade(config, "head")


@pytest.fixture
def google() -> FakeGoogle:
    return FakeGoogle()


@pytest.fixture
def client(google: FakeGoogle) -> TestClient:
    _reset_database()
    return TestClient(
        create_app(
            _settings(), signing_key_resolver=resolver(), calendar_providers={"google": google}
        )
    )


def _connect(client: TestClient, subject: str) -> dict[str, object]:
    headers = auth_headers(subject)
    started = client.post("/api/v1/calendar/connections/google/authorize", headers=headers)
    assert started.status_code == 200
    url = started.json()["authorization_url"]
    query = parse_qs(urlparse(url).query)
    assert query["redirect_uri"] == [f"{APP_URL}/integrations/calendar/google/callback"]
    response = client.post(
        "/api/v1/calendar/connections/google/callback",
        json={"code": "good-code", "state": query["state"][0]},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()  # type: ignore[no-any-return]


def _range() -> dict[str, str]:
    start = datetime.now(UTC) - timedelta(hours=1)
    return {"start": start.isoformat(), "end": (start + timedelta(days=7)).isoformat()}


def test_connect_list_and_disconnect(client: TestClient, google: FakeGoogle) -> None:
    headers = auth_headers("user_calendar")
    providers = client.get("/api/v1/calendar/providers", headers=headers).json()
    assert providers == [
        {"provider": "google", "available": True},
        {"provider": "microsoft", "available": False},
    ]

    connection = _connect(client, "user_calendar")
    assert connection["account_email"] == "member@example.com"
    assert connection["status"] == "active"

    events = client.get("/api/v1/calendar/events", params=_range(), headers=headers)
    assert events.status_code == 200
    assert [(event["title"], event["occasion"]) for event in events.json()] == [
        ("Standup", "work"),
        ("Anniversary dinner", "date"),
    ]

    engine = create_engine(os.environ["DATABASE_URL"])
    try:
        with engine.connect() as database:
            stored = database.execute(
                text("SELECT encrypted_refresh_token FROM calendar_connections")
            ).scalar_one()
    finally:
        engine.dispose()
    assert "refresh" not in stored.split(":", 2)[2]

    # Another member sees none of it.
    other = auth_headers("user_other")
    assert client.get("/api/v1/calendar/connections", headers=other).json() == []
    assert client.get("/api/v1/calendar/events", params=_range(), headers=other).json() == []
    assert (
        client.delete(f"/api/v1/calendar/connections/{connection['id']}", headers=other).status_code
        == 404
    )

    deleted = client.delete(f"/api/v1/calendar/connections/{connection['id']}", headers=headers)
    assert deleted.status_code == 204
    assert google.revoked
    assert client.get("/api/v1/calendar/events", params=_range(), headers=headers).json() == []


def test_a_state_cannot_be_replayed_after_a_failed_exchange(client: TestClient) -> None:
    headers = auth_headers("user_replay")
    url = client.post("/api/v1/calendar/connections/google/authorize", headers=headers).json()[
        "authorization_url"
    ]
    state = parse_qs(urlparse(url).query)["state"][0]

    failed = client.post(
        "/api/v1/calendar/connections/google/callback",
        json={"code": "bad-code", "state": state},
        headers=headers,
    )
    replayed = client.post(
        "/api/v1/calendar/connections/google/callback",
        json={"code": "good-code", "state": state},
        headers=headers,
    )

    assert failed.status_code == 422
    assert failed.json()["code"] == "authorization_failed"
    assert replayed.status_code == 422
    assert replayed.json()["code"] == "invalid_oauth_state"


def test_hiding_an_event_and_deselecting_a_calendar(client: TestClient) -> None:
    headers = auth_headers("user_hide")
    connection = _connect(client, "user_hide")
    events = client.get("/api/v1/calendar/events", params=_range(), headers=headers).json()

    hidden = client.patch(
        f"/api/v1/calendar/events/{events[0]['id']}", json={"is_hidden": True}, headers=headers
    )
    assert hidden.status_code == 200
    visible = client.get("/api/v1/calendar/events", params=_range(), headers=headers).json()
    assert [event["title"] for event in visible] == ["Anniversary dinner"]

    source = connection["sources"][0]  # type: ignore[index]
    updated = client.patch(
        f"/api/v1/calendar/connections/{connection['id']}/sources/{source['id']}",
        json={"is_selected": False},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["sources"][0]["is_selected"] is False
    assert client.get("/api/v1/calendar/events", params=_range(), headers=headers).json() == []


def test_a_revoked_grant_reports_reconnect(client: TestClient, google: FakeGoogle) -> None:
    headers = auth_headers("user_revoked")
    connection = _connect(client, "user_revoked")
    google.fail_refresh = True

    synced = client.post(f"/api/v1/calendar/connections/{connection['id']}/sync", headers=headers)

    assert synced.status_code == 200
    assert synced.json()["status"] == "reauth_required"
    # Cached events stay readable.
    assert len(client.get("/api/v1/calendar/events", params=_range(), headers=headers).json()) == 2


def test_an_unconfigured_provider_is_unavailable(client: TestClient) -> None:
    response = client.post(
        "/api/v1/calendar/connections/microsoft/authorize", headers=auth_headers("user_ms")
    )
    assert response.status_code == 503
    assert response.json()["code"] == "calendar_provider_not_configured"


def test_rejected_app_credentials_are_not_reported_as_an_outage(client: TestClient) -> None:
    headers = auth_headers("user_misconfigured")
    url = client.post("/api/v1/calendar/connections/google/authorize", headers=headers).json()[
        "authorization_url"
    ]
    state = parse_qs(urlparse(url).query)["state"][0]

    response = client.post(
        "/api/v1/calendar/connections/google/callback",
        json={"code": "misconfigured", "state": state},
        headers=headers,
    )

    assert response.status_code == 422
    assert response.json()["code"] == "calendar_client_rejected"
