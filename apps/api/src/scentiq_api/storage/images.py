"""Private image storage. Azure authenticates exclusively with managed identity."""

from contextlib import suppress
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Protocol
from uuid import UUID

from azure.core.exceptions import ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, ContentSettings

from scentiq_api.config import Settings
from scentiq_api.errors import service_unavailable


class ImageStorage(Protocol):
    def write(self, path: str, data: bytes) -> None: ...
    def read(self, path: str) -> bytes: ...
    def delete(self, path: str) -> None: ...
    def delete_user(self, user_id: UUID) -> None: ...


class LocalImageStorage:
    def __init__(self, directory: Path) -> None:
        self.directory = directory.resolve()

    def _path(self, path: str) -> Path:
        target = (self.directory / path).resolve()
        if not target.is_relative_to(self.directory):
            raise ValueError("Image path must remain inside storage")
        return target

    def write(self, path: str, data: bytes) -> None:
        target = self._path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        try:
            with NamedTemporaryFile(dir=target.parent, suffix=".tmp", delete=False) as pending:
                temporary = Path(pending.name)
                pending.write(data)
            temporary.replace(target)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def read(self, path: str) -> bytes:
        return self._path(path).read_bytes()

    def delete(self, path: str) -> None:
        self._path(path).unlink(missing_ok=True)

    def delete_user(self, user_id: UUID) -> None:
        directory = self._path(f"users/{user_id}")
        for file in directory.rglob("*.webp"):
            file.unlink()


class AzureImageStorage:
    def __init__(self, settings: Settings) -> None:
        assert settings.azure_storage_account_url is not None
        credential = DefaultAzureCredential(managed_identity_client_id=settings.azure_client_id)
        service = BlobServiceClient(settings.azure_storage_account_url, credential=credential)
        self.container = service.get_container_client(settings.custom_image_container)

    def write(self, path: str, data: bytes) -> None:
        self.container.get_blob_client(path).upload_blob(
            data, overwrite=True, content_settings=ContentSettings(content_type="image/webp")
        )

    def read(self, path: str) -> bytes:
        return self.container.get_blob_client(path).download_blob().readall()

    def delete(self, path: str) -> None:
        with suppress(ResourceNotFoundError):
            self.container.get_blob_client(path).delete_blob()

    def delete_user(self, user_id: UUID) -> None:
        for blob in self.container.list_blobs(name_starts_with=f"users/{user_id}/"):
            self.delete(blob.name)


def image_storage(settings: Settings) -> ImageStorage:
    if settings.azure_storage_account_url:
        return AzureImageStorage(settings)
    if settings.environment in {"development", "test"} and settings.local_custom_image_directory:
        return LocalImageStorage(Path(settings.local_custom_image_directory))
    raise service_unavailable("image_storage_unavailable", "Image storage is not configured.")
