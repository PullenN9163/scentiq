from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import uuid4

from azure.core.credentials import TokenCredential
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, ContentSettings
from azure.storage.queue import QueueServiceClient


@dataclass
class HybridQueueMessage:
    id: str
    body: str
    dequeue_count: int = 0
    pop_receipt: str | None = None


class HybridTransport(Protocol):
    def upload_json(self, path: str, payload: dict[str, Any]) -> None: ...

    def download_json(self, path: str) -> dict[str, Any]: ...

    def enqueue(self, queue: str, payload: dict[str, Any]) -> None: ...

    def receive(self, queue: str) -> HybridQueueMessage | None: ...

    def renew(
        self,
        queue: str,
        message: HybridQueueMessage,
        *,
        visibility_timeout: int,
    ) -> None: ...

    def delete(self, queue: str, message: HybridQueueMessage) -> None: ...


class InMemoryHybridTransport:
    def __init__(self) -> None:
        self.blobs: dict[str, str] = {}
        self.queues: dict[str, list[HybridQueueMessage]] = {}

    def message(self, body: str) -> HybridQueueMessage:
        return HybridQueueMessage(id=str(uuid4()), body=body)

    def upload_json(self, path: str, payload: dict[str, Any]) -> None:
        self.blobs[path] = json.dumps(payload, separators=(",", ":"), sort_keys=True)

    def download_json(self, path: str) -> dict[str, Any]:
        loaded = json.loads(self.blobs[path])
        if not isinstance(loaded, dict):
            raise ValueError("JSON blob must contain an object")
        return loaded

    def enqueue(self, queue: str, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        self.queues.setdefault(queue, []).append(self.message(body))

    def receive(self, queue: str) -> HybridQueueMessage | None:
        messages = self.queues.setdefault(queue, [])
        if not messages:
            return None
        message = messages[0]
        message.dequeue_count += 1
        return message

    def delete(self, queue: str, message: HybridQueueMessage) -> None:
        messages = self.queues.setdefault(queue, [])
        self.queues[queue] = [candidate for candidate in messages if candidate.id != message.id]

    def renew(
        self,
        queue: str,
        message: HybridQueueMessage,
        *,
        visibility_timeout: int,
    ) -> None:
        del queue, message, visibility_timeout


class AzureHybridTransport:
    def __init__(
        self,
        *,
        container_client: Any,
        queue_client_factory: Callable[[str], Any],
    ) -> None:
        self._container = container_client
        self._queue_client_factory = queue_client_factory

    @classmethod
    def from_account_urls(
        cls,
        *,
        blob_account_url: str,
        queue_account_url: str,
        container: str = "system",
        credential: TokenCredential | None = None,
    ) -> AzureHybridTransport:
        resolved_credential = credential or DefaultAzureCredential()
        blob_service = BlobServiceClient(blob_account_url, credential=resolved_credential)
        queue_service = QueueServiceClient(queue_account_url, credential=resolved_credential)
        return cls(
            container_client=blob_service.get_container_client(container),
            queue_client_factory=queue_service.get_queue_client,
        )

    def upload_json(self, path: str, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        self._container.get_blob_client(path).upload_blob(
            body,
            overwrite=True,
            content_settings=ContentSettings(content_type="application/json"),
        )

    def download_json(self, path: str) -> dict[str, Any]:
        raw = self._container.get_blob_client(path).download_blob().readall()
        loaded = json.loads(raw)
        if not isinstance(loaded, dict):
            raise ValueError("JSON blob must contain an object")
        return loaded

    def enqueue(self, queue: str, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        self._queue_client_factory(queue).send_message(body)

    def receive(self, queue: str) -> HybridQueueMessage | None:
        messages = self._queue_client_factory(queue).receive_messages(
            messages_per_page=1,
            visibility_timeout=60,
        )
        message = next(iter(messages), None)
        if message is None:
            return None
        return HybridQueueMessage(
            id=message.id,
            body=message.content,
            dequeue_count=message.dequeue_count,
            pop_receipt=message.pop_receipt,
        )

    def delete(self, queue: str, message: HybridQueueMessage) -> None:
        if message.pop_receipt is None:
            raise ValueError("Azure queue message has no pop receipt")
        self._queue_client_factory(queue).delete_message(message.id, message.pop_receipt)

    def renew(
        self,
        queue: str,
        message: HybridQueueMessage,
        *,
        visibility_timeout: int,
    ) -> None:
        if message.pop_receipt is None:
            raise ValueError("Azure queue message has no pop receipt")
        updated = self._queue_client_factory(queue).update_message(
            message.id,
            message.pop_receipt,
            visibility_timeout=visibility_timeout,
        )
        message.pop_receipt = updated.pop_receipt
