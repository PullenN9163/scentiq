"""HTTP plumbing shared by the calendar providers.

Every failure becomes a `CalendarProviderError` with a short code. Provider
response bodies and URLs are never propagated: token-endpoint URLs and bodies
can carry codes and secrets.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from typing import Any

import httpx

from scentiq_api.integrations.calendar.base import (
    DEFAULT_TIMEOUT,
    CalendarAuthError,
    CalendarProviderError,
    TokenSet,
)

MAX_PAGES = 20


class ProviderHttp:
    def __init__(
        self,
        *,
        transport: httpx.BaseTransport | None = None,
        timeout: httpx.Timeout = DEFAULT_TIMEOUT,
    ) -> None:
        self._transport = transport
        self._timeout = timeout

    def _send(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        try:
            with httpx.Client(transport=self._transport, timeout=self._timeout) as client:
                return client.request(method, url, **kwargs)
        except httpx.HTTPError:
            raise CalendarProviderError("provider_unavailable") from None

    def token_request(self, url: str, form: dict[str, str]) -> TokenSet:
        response = self._send("POST", url, data=form, headers={"Accept": "application/json"})
        payload = _json(response)
        if response.status_code >= 500:
            raise CalendarProviderError("provider_unavailable")
        if response.status_code >= 400:
            if payload.get("error") in ("invalid_grant", "invalid_token", "unauthorized_client"):
                raise CalendarAuthError()
            raise CalendarProviderError("token_request_failed")
        access_token = payload.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise CalendarProviderError("token_request_failed")
        refresh_token = payload.get("refresh_token")
        scope = payload.get("scope")
        return TokenSet(
            access_token=access_token,
            refresh_token=refresh_token if isinstance(refresh_token, str) else None,
            scopes=frozenset(scope.split()) if isinstance(scope, str) else frozenset(),
        )

    def get_json(
        self,
        url: str,
        access_token: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        response = self._send(
            "GET",
            url,
            params=params,
            headers={"Authorization": f"Bearer {access_token}", **(headers or {})},
        )
        if response.status_code == 401:
            raise CalendarAuthError()
        if response.status_code in (404, 410):
            raise CalendarProviderError("calendar_not_found")
        if response.status_code == 429:
            raise CalendarProviderError("rate_limited")
        if response.status_code >= 500:
            raise CalendarProviderError("provider_unavailable")
        if response.status_code >= 400:
            raise CalendarProviderError("provider_rejected")
        return _json(response)

    def post_form(self, url: str, form: dict[str, str]) -> None:
        self._send("POST", url, data=form)


def _json(response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}


def parse_instant(value: str) -> datetime:
    """An ISO-8601 instant as an aware UTC datetime; a missing offset means UTC."""
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def all_day_instant(value: str) -> datetime:
    """An all-day date, stored as midnight UTC of that calendar date."""
    return datetime.combine(date.fromisoformat(value), time.min, tzinfo=UTC)


def rfc3339(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
