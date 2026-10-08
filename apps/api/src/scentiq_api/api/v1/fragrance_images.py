from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from scentiq_api.auth import AuthenticatedUser, CurrentUserDependency
from scentiq_api.config import Settings
from scentiq_api.errors import ApiError
from scentiq_api.services.fragrance_images import MAX_IMAGE_BYTES, FragranceImageService
from scentiq_api.storage.images import image_storage


def create_fragrance_image_router(
    get_session: object, current_user: CurrentUserDependency, settings: Settings
) -> APIRouter:
    router = APIRouter(prefix="/fragrances", tags=["fragrances"])

    @router.get(
        "/{fragrance_id}/image",
        response_class=Response,
        responses={
            200: {"content": {"image/webp": {"schema": {"type": "string", "format": "binary"}}}}
        },
    )
    def get_image(
        fragrance_id: UUID,
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user)],
    ) -> Response:
        data = FragranceImageService(session, image_storage(settings)).read(
            user.user_id, fragrance_id
        )
        return Response(
            data,
            media_type="image/webp",
            headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
        )

    @router.put(
        "/{fragrance_id}/image",
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {
                    mime: {"schema": {"type": "string", "format": "binary"}}
                    for mime in ("image/jpeg", "image/png", "image/webp")
                },
            }
        },
    )
    async def put_image(
        fragrance_id: UUID,
        request: Request,
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user)],
    ) -> dict[str, str]:
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > MAX_IMAGE_BYTES:
                raise ApiError(
                    status_code=413,
                    code="image_too_large",
                    message="Images must be 5 MB or smaller.",
                )
        url = FragranceImageService(session, image_storage(settings)).replace(
            user.user_id,
            fragrance_id,
            bytes(data),
            request.headers.get("content-type", "").split(";")[0],
        )
        session.commit()
        return {"image_url": url}

    @router.delete("/{fragrance_id}/image", status_code=204)
    def delete_image(
        fragrance_id: UUID,
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user)],
    ) -> Response:
        FragranceImageService(session, image_storage(settings)).delete(user.user_id, fragrance_id)
        session.commit()
        return Response(status_code=204)

    return router
