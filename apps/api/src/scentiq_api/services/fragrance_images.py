"""Owned custom image validation, normalized storage, and authenticated reads."""

from datetime import UTC, datetime
from io import BytesIO
from uuid import UUID

from azure.core.exceptions import AzureError, ResourceNotFoundError
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session

from scentiq_api.errors import ApiError, not_found, service_unavailable, unprocessable
from scentiq_api.models import Fragrance
from scentiq_api.storage.images import ImageStorage

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
_FORMATS = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}


def normalize_image(data: bytes, content_type: str) -> bytes:
    if len(data) > MAX_IMAGE_BYTES:
        raise ApiError(
            status_code=413, code="image_too_large", message="Images must be 5 MB or smaller."
        )
    if content_type not in _FORMATS:
        raise unprocessable("unsupported_image", "Choose a JPEG, PNG, or WebP image.")
    try:
        with Image.open(BytesIO(data)) as source:
            if source.format != _FORMATS[content_type]:
                raise ValueError("Content type does not match image bytes")
            if source.width * source.height > MAX_IMAGE_PIXELS:
                raise ValueError("Image dimensions are too large")
            source.verify()
        with Image.open(BytesIO(data)) as source:
            oriented = ImageOps.exif_transpose(source)
            oriented.thumbnail((1600, 1600))
            # A fresh image discards EXIF, XMP, text chunks, and color-profile metadata.
            mode = "RGBA" if "A" in oriented.getbands() else "RGB"
            normalized = Image.new(mode, oriented.size)
            normalized.paste(oriented.convert(mode))
            output = BytesIO()
            normalized.save(output, format="WEBP", quality=88)
            return output.getvalue()
    except (
        ValueError,
        OSError,
        UnidentifiedImageError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as error:
        raise unprocessable(
            "invalid_image", "This file could not be decoded as a supported image."
        ) from error


class FragranceImageService:
    def __init__(self, session: Session, storage: ImageStorage) -> None:
        self.session = session
        self.storage = storage

    def _owned(self, user_id: UUID, fragrance_id: UUID) -> Fragrance:
        item = self.session.scalar(
            select(Fragrance)
            .where(Fragrance.id == fragrance_id, Fragrance.owner_user_id == user_id)
            .with_for_update()
        )
        if item is None:
            raise not_found("Custom fragrance not found")
        return item

    def _path(self, user_id: UUID, fragrance_id: UUID, path: str | None) -> str:
        expected = f"users/{user_id}/fragrances/{fragrance_id}/image.webp"
        if path != expected:
            raise not_found("Image not found")
        return expected

    def replace(self, user_id: UUID, fragrance_id: UUID, data: bytes, content_type: str) -> str:
        item = self._owned(user_id, fragrance_id)
        normalized = normalize_image(data, content_type)
        path = f"users/{user_id}/fragrances/{fragrance_id}/image.webp"
        try:
            self.storage.write(path, normalized)
        except AzureError as error:
            raise service_unavailable(
                "image_storage_unavailable", "Image storage is temporarily unavailable."
            ) from error
        item.image_blob_path = path
        item.updated_at = datetime.now(UTC)
        self.session.flush()
        return f"/api/fragrances/{fragrance_id}/image"

    def read(self, user_id: UUID, fragrance_id: UUID) -> bytes:
        item = self._owned(user_id, fragrance_id)
        path = self._path(user_id, fragrance_id, item.image_blob_path)
        try:
            return self.storage.read(path)
        except (FileNotFoundError, ResourceNotFoundError) as error:
            raise not_found("Image not found") from error
        except AzureError as error:
            raise service_unavailable(
                "image_storage_unavailable", "Image storage is temporarily unavailable."
            ) from error

    def delete(self, user_id: UUID, fragrance_id: UUID) -> None:
        item = self._owned(user_id, fragrance_id)
        if item.image_blob_path:
            try:
                self.storage.delete(self._path(user_id, fragrance_id, item.image_blob_path))
            except AzureError as error:
                raise service_unavailable(
                    "image_storage_unavailable", "Image storage is temporarily unavailable."
                ) from error
        item.image_blob_path = None
        self.session.flush()
