"""The provider-neutral calendar contract Google and Microsoft both implement."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol

import httpx

CalendarProviderName = Literal["google", "microsoft"]
PROVIDERS: tuple[CalendarProviderName, ...] = ("google", "microsoft")
DEFAULT_TIMEOUT = httpx.Timeout(10.0)


class CalendarProviderError(Exception):
    """A provider call failed. `code` is safe to store and show."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class CalendarAuthError(CalendarProviderError):
    """The grant is no longer valid; the member must reconnect."""

    def __init__(self, code: str = "reauth_required") -> None:
        super().__init__(code)


@dataclass(frozen=True)
class TokenSet:
    access_token: str
    # Present on the first exchange, and whenever the provider rotates it.
    refresh_token: str | None
    scopes: frozenset[str]


@dataclass(frozen=True)
class ProviderCalendar:
    id: str
    name: str
    color: str | None
    is_primary: bool


@dataclass(frozen=True)
class ProviderEvent:
    id: str
    title: str
    starts_at: datetime
    ends_at: datetime
    is_all_day: bool
    location: str | None


class CalendarProvider(Protocol):
    name: CalendarProviderName
    # Scopes the grant must include for ScentIQ to read events.
    required_scopes: frozenset[str]

    def authorization_url(self, *, state: str, code_challenge: str, redirect_uri: str) -> str: ...

    def exchange_code(self, *, code: str, code_verifier: str, redirect_uri: str) -> TokenSet: ...

    def refresh(self, refresh_token: str) -> TokenSet: ...

    def account_email(self, access_token: str) -> str: ...

    def list_calendars(self, access_token: str) -> list[ProviderCalendar]: ...

    def list_events(
        self, access_token: str, calendar_id: str, start: datetime, end: datetime
    ) -> list[ProviderEvent]: ...

    def revoke(self, refresh_token: str) -> None: ...
