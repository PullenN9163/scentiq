from io import BytesIO
from pathlib import Path

import pytest
from domain_fixtures import make_brand, make_fragrance, make_user
from PIL import Image, PngImagePlugin
from sqlalchemy.orm import Session

from scentiq_api.errors import ApiError
from scentiq_api.repositories import IdentityRepository
from scentiq_api.services.fragrance_images import (
    MAX_IMAGE_BYTES,
    FragranceImageService,
    normalize_image,
)
from scentiq_api.services.identity import IdentityEventService
from scentiq_api.storage.images import LocalImageStorage


def png_bytes() -> bytes:
    output = BytesIO()
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text("private", "location data")
    Image.new("RGB", (32, 48), "green").save(output, format="PNG", pnginfo=metadata)
    return output.getvalue()


def test_normalization_removes_metadata_and_uses_webp() -> None:
    result = normalize_image(png_bytes(), "image/png")
    with Image.open(BytesIO(result)) as image:
        assert image.format == "WEBP"
        assert image.size == (32, 48)
        assert "private" not in image.info
        assert "exif" not in image.info


@pytest.mark.parametrize(
    "data,mime",
    [
        (b"fake", "image/png"),
        (png_bytes(), "image/jpeg"),
        (b"x" * (MAX_IMAGE_BYTES + 1), "image/png"),
    ],
    ids=["invalid", "mismatch", "oversize"],
)
def test_rejects_invalid_bytes_mismatch_and_oversize(data: bytes, mime: str) -> None:
    with pytest.raises(ApiError) as error:
        normalize_image(data, mime)
    assert error.value.status_code in {413, 422}


def test_only_owner_can_replace_read_or_delete_custom_image(
    session: Session, tmp_path: Path
) -> None:
    owner = make_user(session, email="owner@images.test")
    other = make_user(session, email="other@images.test")
    custom = make_fragrance(
        session,
        brand=make_brand(session, name="Private", owner_user_id=owner.id),
        name="Custom",
        owner_user_id=owner.id,
    )
    shared = make_fragrance(session, brand=make_brand(session, name="Shared"), name="Catalog")
    storage = LocalImageStorage(tmp_path)
    service = FragranceImageService(session, storage)
    for target in [custom, shared]:
        with pytest.raises(ApiError) as error:
            service.replace(other.id, target.id, png_bytes(), "image/png")
        assert error.value.status_code == 404
    service.replace(owner.id, custom.id, png_bytes(), "image/png")
    assert custom.image_blob_path is not None
    assert custom.image_blob_path.startswith(f"users/{owner.id}/fragrances/{custom.id}/")
    assert service.read(owner.id, custom.id)
    with pytest.raises(ApiError):
        service.read(other.id, custom.id)
    storage.delete_user(owner.id)
    assert not list(tmp_path.rglob("*.webp"))
    service.replace(owner.id, custom.id, png_bytes(), "image/png")
    service.delete(owner.id, custom.id)
    assert custom.image_blob_path is None
    assert not list(tmp_path.rglob("*.webp"))


def test_account_deletion_cleans_private_images_before_database_purge(
    session: Session, tmp_path: Path
) -> None:
    user = make_user(session, email="delete@images.test", subject="delete-images")
    custom = make_fragrance(
        session,
        brand=make_brand(session, name="DeletePrivate", owner_user_id=user.id),
        name="DeleteCustom",
        owner_user_id=user.id,
    )
    storage = LocalImageStorage(tmp_path)
    FragranceImageService(session, storage).replace(user.id, custom.id, png_bytes(), "image/png")
    service = IdentityEventService(IdentityRepository(session), images=storage)
    assert service.handle_user_deleted(event_id="evt_images", subject="delete-images")
    assert not list(tmp_path.rglob("*.webp"))
