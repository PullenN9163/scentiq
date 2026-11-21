from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from scentiq_api.auth import AuthenticatedUser, CurrentUserDependency
from scentiq_api.repositories import LayeringRepository
from scentiq_api.schemas import LayeringMode, LayeringSuggestion
from scentiq_api.schemas.layering import (
    LayeringGoal,
    LayeringIntelligencePage,
    LayeringStackRatingRequest,
    LayeringStackRenameRequest,
    LayeringStackRequest,
    LayeringStackSaveRequest,
    LayeringStackSuggestion,
    LayeringStackWearRequest,
    LayeringStackWearResponse,
    SavedLayeringStack,
)
from scentiq_api.services import LayeringService


def create_layering_router(get_session: object, current_user: CurrentUserDependency) -> APIRouter:
    router = APIRouter(prefix="/layering", tags=["layering"])

    @router.get("/suggestions", response_model=list[LayeringSuggestion])
    def suggestions(
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user)],
        mode: LayeringMode = "safe",
        limit: Annotated[int, Query(ge=1, le=50)] = 12,
        first_id: UUID | None = None,
        second_id: UUID | None = None,
    ) -> list[LayeringSuggestion]:
        return LayeringService(LayeringRepository(session)).suggest(
            user.user_id,
            mode=mode,
            limit=limit,
            first_id=first_id,
            second_id=second_id,
        )

    @router.get("/intelligence", response_model=LayeringIntelligencePage)
    def intelligence(
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user)],
        anchor_id: UUID | None = None,
        mode: LayeringMode = "balanced",
        goal: LayeringGoal | None = None,
    ) -> LayeringIntelligencePage:
        return LayeringService(LayeringRepository(session)).intelligence_page(
            user.user_id, anchor_id=anchor_id, mode=mode, goal=goal
        )

    @router.get("/stacks/suggestions", response_model=list[LayeringStackSuggestion])
    def stack_suggestions(
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user)],
        anchor_id: UUID | None = None,
        mode: LayeringMode = "balanced",
        goal: LayeringGoal | None = None,
        limit: Annotated[int, Query(ge=1, le=50)] = 12,
        include_triples: bool = True,
        stack_size: Literal[2, 3] | None = None,
    ) -> list[LayeringStackSuggestion]:
        return LayeringService(LayeringRepository(session)).stack_suggestions(
            user.user_id,
            anchor_id=anchor_id,
            mode=mode,
            goal=goal,
            limit=limit,
            include_triples=include_triples,
            stack_size=stack_size,
        )

    @router.post("/stacks/evaluate", response_model=LayeringStackSuggestion)
    def evaluate(
        request: LayeringStackRequest,
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user)],
    ) -> LayeringStackSuggestion:
        return LayeringService(LayeringRepository(session)).evaluate_stack(
            user.user_id, request.fragrance_ids, mode=request.mode, goal=request.goal
        )

    @router.get("/stacks", response_model=list[SavedLayeringStack])
    def saved_stacks(
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user)],
    ) -> list[SavedLayeringStack]:
        return LayeringService(LayeringRepository(session)).saved_stacks(user.user_id)

    @router.post("/stacks", response_model=SavedLayeringStack, status_code=201)
    def save(
        request: LayeringStackSaveRequest,
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user)],
    ) -> SavedLayeringStack:
        result = LayeringService(LayeringRepository(session)).save_stack(
            user.user_id,
            request.fragrance_ids,
            name=request.name,
            mode=request.mode,
            goal=request.goal,
            notes=request.notes,
        )
        session.commit()
        return result

    @router.patch("/stacks/{stack_id}", response_model=SavedLayeringStack)
    def rename(
        stack_id: UUID,
        request: LayeringStackRenameRequest,
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user)],
    ) -> SavedLayeringStack:
        result = LayeringService(LayeringRepository(session)).rename_stack(
            user.user_id, stack_id, request.name
        )
        session.commit()
        return result

    @router.delete("/stacks/{stack_id}", status_code=204)
    def delete(
        stack_id: UUID,
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user)],
    ) -> Response:
        LayeringService(LayeringRepository(session)).delete_stack(user.user_id, stack_id)
        session.commit()
        return Response(status_code=204)

    @router.get("/stacks/{stack_id}/wears", response_model=list[LayeringStackWearResponse])
    def history(
        stack_id: UUID,
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user)],
    ) -> list[LayeringStackWearResponse]:
        return LayeringService(LayeringRepository(session)).history(user.user_id, stack_id)

    @router.post(
        "/stacks/{stack_id}/wears", response_model=LayeringStackWearResponse, status_code=201
    )
    def wear(
        stack_id: UUID,
        request: LayeringStackWearRequest,
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user)],
    ) -> LayeringStackWearResponse:
        result = LayeringService(LayeringRepository(session)).log_stack_wear(
            user.user_id,
            stack_id,
            worn_at=request.worn_at,
            rating=request.rating,
            notes=request.notes,
        )
        session.commit()
        return result

    @router.patch(
        "/stacks/{stack_id}/wears/{wear_id}/rating", response_model=LayeringStackWearResponse
    )
    def rate(
        stack_id: UUID,
        wear_id: UUID,
        request: LayeringStackRatingRequest,
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user)],
    ) -> LayeringStackWearResponse:
        result = LayeringService(LayeringRepository(session)).rate_stack_wear(
            user.user_id, stack_id, wear_id, rating=request.rating
        )
        session.commit()
        return result

    return router
