"""Google Calendar over OAuth 2.0 with PKCE."""

from __future__ import annotations

import contextlib
from datetime import datetime
from typing import Any
from urllib.parse import quote, urlencode

import httpx

from scentiq_api.integrations.calendar.base import (
    DEFAULT_TIMEOUT,
    CalendarProviderError,
    CalendarProviderName,
    ProviderCalendar,
    ProviderEvent,
    TokenSet,
)
from scentiq_api.integrations.calendar.http import (
    MAX_PAGES,
    ProviderHttp,
    all_day_instant,
    parse_instant,
    rfc3339,
)

AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
CALENDAR_API = "https://www.googleapis.com/calendar/v3"

CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.readonly"
SCOPES = ("openid", "email", CALENDAR_SCOPE)

# Status markers rather than meetings; they would read as an event every day.
_IGNORED_EVENT_TYPES = frozenset({"workingLocation"})


class GoogleCalendarProvider:
    name: CalendarProviderName = "google"
    required_scopes = frozenset({CALENDAR_SCOPE})

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        transport: httpx.BaseTransport | None = None,
        timeout: httpx.Timeout = DEFAULT_TIMEOUT,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._http = ProviderHttp(transport=transport, timeout=timeout)

    def authorization_url(self, *, state: str, code_challenge: str, redirect_uri: str) -> str:
        parameters = {
            "client_id": self._client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(SCOPES),
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            # Offline access plus a forced consent prompt is what makes Google
            # return a refresh token, including on a reconnect.
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
        }
        return f"{AUTHORIZATION_URL}?{urlencode(parameters)}"

    def exchange_code(self, *, code: str, code_verifier: str, redirect_uri: str) -> TokenSet:
        return self._http.token_request(
            TOKEN_URL,
            {
                "grant_type": "authorization_code",
                "code": code,
                "code_verifier": code_verifier,
                "redirect_uri": redirect_uri,
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            },
        )

    def refresh(self, refresh_token: str) -> TokenSet:
        return self._http.token_request(
            TOKEN_URL,
            {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            },
        )

    def account_email(self, access_token: str) -> str:
        payload = self._http.get_json(USERINFO_URL, access_token)
        email = payload.get("email")
        if not isinstance(email, str) or "@" not in email:
            raise CalendarProviderError("account_email_missing")
        return email.lower()

    def list_calendars(self, access_token: str) -> list[ProviderCalendar]:
        calendars: list[ProviderCalendar] = []
        page_token: str | None = None
        for _ in range(MAX_PAGES):
            parameters: dict[str, Any] = {"minAccessRole": "reader", "maxResults": 250}
            if page_token:
                parameters["pageToken"] = page_token
            payload = self._http.get_json(
                f"{CALENDAR_API}/users/me/calendarList", access_token, params=parameters
            )
            for item in payload.get("items") or []:
                if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                    continue
                name = item.get("summaryOverride") or item.get("summary") or item["id"]
                calendars.append(
                    ProviderCalendar(
                        id=item["id"],
                        name=str(name)[:200],
                        color=item.get("backgroundColor"),
                        is_primary=bool(item.get("primary")),
                    )
                )
            page_token = payload.get("nextPageToken")
            if not page_token:
                break
        return calendars

    def list_events(
        self, access_token: str, calendar_id: str, start: datetime, end: datetime
    ) -> list[ProviderEvent]:
        events: list[ProviderEvent] = []
        page_token: str | None = None
        url = f"{CALENDAR_API}/calendars/{quote(calendar_id, safe='')}/events"
        for _ in range(MAX_PAGES):
            parameters: dict[str, Any] = {
                # Expands recurring events into their occurrences.
                "singleEvents": "true",
                "orderBy": "startTime",
                "timeMin": rfc3339(start),
                "timeMax": rfc3339(end),
                "maxResults": 250,
            }
            if page_token:
                parameters["pageToken"] = page_token
            payload = self._http.get_json(url, access_token, params=parameters)
            for item in payload.get("items") or []:
                event = _event_from(item)
                if event is not None:
                    events.append(event)
            page_token = payload.get("nextPageToken")
            if not page_token:
                break
        return events

    def revoke(self, refresh_token: str) -> None:
        # Best effort: the grant is deleted locally regardless.
        with contextlib.suppress(CalendarProviderError):
            self._http.post_form(REVOKE_URL, {"token": refresh_token})


def _event_from(item: Any) -> ProviderEvent | None:
    if not isinstance(item, dict) or not isinstance(item.get("id"), str):
        return None
    if item.get("status") == "cancelled" or item.get("eventType") in _IGNORED_EVENT_TYPES:
        return None
    start, end = item.get("start") or {}, item.get("end") or {}
    try:
        if "dateTime" in start:
            starts_at = parse_instant(start["dateTime"])
            ends_at = parse_instant(end.get("dateTime", start["dateTime"]))
            is_all_day = False
        elif "date" in start:
            starts_at = all_day_instant(start["date"])
            ends_at = all_day_instant(end.get("date", start["date"]))
            is_all_day = True
        else:
            return None
    except TypeError, ValueError:
        return None
    title = item.get("summary")
    location = item.get("location")
    return ProviderEvent(
        id=item["id"],
        # Events shared as free/busy only carry no title.
        title=(title.strip() if isinstance(title, str) and title.strip() else "Busy")[:200],
        starts_at=starts_at,
        ends_at=max(ends_at, starts_at),
        is_all_day=is_all_day,
        location=location.strip()[:160] if isinstance(location, str) and location.strip() else None,
    )
