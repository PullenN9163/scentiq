"""Authenticated NDJSON advisor; provider payloads stay within the service."""

import json
from collections.abc import AsyncIterator, Callable, Coroutine
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from fastapi.routing import APIRoute
from sqlalchemy.orm import Session
from starlette.types import Message

from scentiq_api.agent.provider import AzureResponsesProvider
from scentiq_api.agent.tools import AgentTools
from scentiq_api.auth import AuthenticatedUser, CurrentUserDependency
from scentiq_api.config import Settings
from scentiq_api.schemas.agent import AgentChatRequest, AgentStreamEvent
from scentiq_api.services.agent import AgentService


class BoundedAgentRoute(APIRoute):
    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        handler = super().get_route_handler()

        async def bounded(request: Request) -> Response:
            size = 0

            async def receive() -> Message:
                nonlocal size
                message = await request.receive()
                if message["type"] == "http.request":
                    size += len(message.get("body", b""))
                    if size > 65536:
                        raise HTTPException(status_code=413, detail="Conversation is too long")
                return message

            return await handler(Request(request.scope, receive=receive))

        return bounded


def build_provider(settings: Settings) -> AzureResponsesProvider | None:
    if (
        not settings.agent_enabled
        or not settings.azure_openai_endpoint
        or not settings.azure_openai_deployment
    ):
        return None
    local_key = settings.azure_openai_api_key
    return AzureResponsesProvider(
        settings.azure_openai_endpoint,
        settings.azure_openai_deployment,
        api_key=local_key.get_secret_value()
        if local_key and not settings.azure_client_id and settings.environment != "production"
        else None,
        client_id=settings.azure_client_id,
    )


def create_agent_router(
    get_session: object,
    current_user: CurrentUserDependency,
    settings: Settings,
    refresh_context: Callable[[Session, UUID], None] | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/agent", tags=["agent"], route_class=BoundedAgentRoute)

    @router.post(
        "/chat",
        responses={
            200: {
                "description": (
                    "NDJSON events: status, tool_started, tool_finished, "
                    "text_delta, card, fallback, done"
                ),
                "content": {"application/x-ndjson": {"schema": {"type": "string"}}},
            }
        },
    )
    async def chat(
        payload: AgentChatRequest,
        request: Request,
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user)],
    ) -> StreamingResponse:
        service = AgentService(
            AgentTools(session, user.user_id, refresh_context),
            build_provider(settings),
            timeout_seconds=settings.agent_timeout_seconds,
            max_tool_calls=settings.agent_max_tool_calls,
            max_iterations=settings.agent_max_turns,
            prompt_version=settings.agent_prompt_version,
        )

        async def events() -> AsyncIterator[str]:
            async for event in service.chat(payload):
                if await request.is_disconnected():
                    break
                validated = AgentStreamEvent.model_validate(event)
                yield (
                    json.dumps(
                        validated.model_dump(mode="json", exclude_none=True), ensure_ascii=False
                    )
                    + "\n"
                )

        return StreamingResponse(
            events(),
            media_type="application/x-ndjson",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        )

    return router
