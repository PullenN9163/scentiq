"""Outlook calendars through Microsoft Graph, over OAuth 2.0 with PKCE.

The `common` tenant accepts work, school and personal Microsoft accounts.
Microsoft rotates refresh tokens on use, which `CalendarService` handles by
storing whichever token each refresh returns.
"""

from __future__ import annotations

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

AUTHORITY = "https://login.microsoftonline.com/common/oauth2/v2.0"
AUTHORIZATION_URL = f"{AUTHORITY}/authorize"
TOKEN_URL = f"{AUTHORITY}/token"
GRAPH_API = "https://graph.microsoft.com/v1.0"
_GRAPH_SCOPE_PREFIX = "https://graph.microsoft.com/"

SCOPES = ("openid", "email", "offline_access", "User.Read", "Calendars.Read")
CALENDAR_SCOPE = "calendars.read"

# Graph returns event times in the zone this header names.
_UTC_PREFERENCE = {"Prefer": 'outlook.timezone="UTC"'}


def _normalise_scopes(scopes: frozenset[str]) -> frozenset[str]:
    """Graph may report `Calendars.Read` or its full URI; compare them as one."""
    return frozenset(scope.removeprefix(_GRAPH_SCOPE_PREFIX).casefold() for scope in scopes)


class MicrosoftCalendarProvider:
    name: CalendarProviderName = "microsoft"
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
            "response_mode": "query",
            "scope": " ".join(SCOPES),
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            # Lets a member with several Microsoft accounts choose which one.
            "prompt": "select_account",
        }
        return f"{AUTHORIZATION_URL}?{urlencode(parameters)}"

    def _token(self, form: dict[str, str]) -> TokenSet:
        tokens = self._http.token_request(
            TOKEN_URL,
            {
                **form,
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "scope": " ".join(SCOPES),
            },
        )
        return TokenSet(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            scopes=_normalise_scopes(tokens.scopes),
        )

    def exchange_code(self, *, code: str, code_verifier: str, redirect_uri: str) -> TokenSet:
        return self._token(
            {
                "grant_type": "authorization_code",
                "code": code,
                "code_verifier": code_verifier,
                "redirect_uri": redirect_uri,
            }
        )

    def refresh(self, refresh_token: str) -> TokenSet:
        return self._token({"grant_type": "refresh_token", "refresh_token": refresh_token})

    def account_email(self, access_token: str) -> str:
        payload = self._http.get_json(
            f"{GRAPH_API}/me", access_token, params={"$select": "mail,userPrincipalName"}
        )
        # Personal accounts often have no `mail`; their sign-in name is the address.
        for candidate in (payload.get("mail"), payload.get("userPrincipalName")):
            if isinstance(candidate, str) and "@" in candidate:
                return candidate.lower()
        raise CalendarProviderError("account_email_missing")

    def _pages(
        self,
        url: str,
        access_token: str,
        params: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        next_url: str | None = url
        next_params: dict[str, Any] | None = params
        for _ in range(MAX_PAGES):
            if next_url is None:
                break
            payload = self._http.get_json(
                next_url, access_token, params=next_params, headers=headers
            )
            items.extend(item for item in payload.get("value") or [] if isinstance(item, dict))
            link = payload.get("@odata.nextLink")
            # The next link already carries every query parameter.
            next_url = link if isinstance(link, str) and link.startswith(GRAPH_API) else None
            next_params = None
        return items

    def list_calendars(self, access_token: str) -> list[ProviderCalendar]:
        calendars: list[ProviderCalendar] = []
        for item in self._pages(
            f"{GRAPH_API}/me/calendars",
            access_token,
            {"$select": "id,name,hexColor,isDefaultCalendar", "$top": 100},
        ):
            if not isinstance(item.get("id"), str):
                continue
            color = item.get("hexColor")
            calendars.append(
                ProviderCalendar(
                    id=item["id"],
                    name=str(item.get("name") or "Calendar")[:200],
                    color=color if isinstance(color, str) and color else None,
                    is_primary=bool(item.get("isDefaultCalendar")),
                )
            )
        return calendars

    def list_events(
        self, access_token: str, calendar_id: str, start: datetime, end: datetime
    ) -> list[ProviderEvent]:
        # calendarView expands recurring series into their occurrences.
        items = self._pages(
            f"{GRAPH_API}/me/calendars/{quote(calendar_id, safe='')}/calendarView",
            access_token,
            {
                "startDateTime": rfc3339(start),
                "endDateTime": rfc3339(end),
                "$select": "id,subject,start,end,isAllDay,isCancelled,location",
                "$orderby": "start/dateTime",
                "$top": 250,
            },
            headers=_UTC_PREFERENCE,
        )
        events = (_event_from(item) for item in items)
        return [event for event in events if event is not None]

    def revoke(self, refresh_token: str) -> None:
        """Microsoft has no per-grant revocation endpoint.

        Revoking would mean signing the member out of every session, which is
        not ScentIQ's to do; deleting the stored grant is what disconnects.
        """


def _event_from(item: dict[str, Any]) -> ProviderEvent | None:
    if not isinstance(item.get("id"), str) or item.get("isCancelled"):
        return None
    start, end = item.get("start") or {}, item.get("end") or {}
    start_value, end_value = start.get("dateTime"), end.get("dateTime")
    if not isinstance(start_value, str):
        return None
    if not isinstance(end_value, str):
        end_value = start_value
    try:
        if item.get("isAllDay"):
            # All-day events arrive as midnight in the preferred zone (UTC).
            starts_at = all_day_instant(start_value[:10])
            ends_at = all_day_instant(end_value[:10])
            is_all_day = True
        else:
            starts_at = parse_instant(start_value)
            ends_at = parse_instant(end_value)
            is_all_day = False
    except TypeError, ValueError:
        return None
    subject = item.get("subject")
    location = (item.get("location") or {}).get("displayName")
    return ProviderEvent(
        id=item["id"],
        title=(subject.strip() if isinstance(subject, str) and subject.strip() else "Busy")[:200],
        starts_at=starts_at,
        ends_at=max(ends_at, starts_at),
        is_all_day=is_all_day,
        location=location.strip()[:160] if isinstance(location, str) and location.strip() else None,
    )
