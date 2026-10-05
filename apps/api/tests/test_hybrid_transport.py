import json

from domain_fixtures import make_brand, make_collection_item, make_fragrance, make_user
from sqlalchemy.orm import Session

from scentiq_api.hybrid import (
    AzureHybridTransport,
    HybridDispatcher,
    HybridResultApplier,
    HybridWorker,
    InMemoryHybridTransport,
)
from scentiq_api.hybrid.contracts import RecommendationJobInput
from scentiq_api.hybrid.processor import process_recommendation
from scentiq_api.models import AsyncJob, RecommendationSnapshot
from scentiq_api.repositories import HybridJobRepository
from scentiq_api.services import HybridJobService


def _pending_job(session: Session) -> AsyncJob:
    user = make_user(session, email="private@example.com")
    brand = make_brand(session, name="House")
    fragrance = make_fragrance(session, brand=brand, name="Scent")
    make_collection_item(session, user=user, fragrance=fragrance, user_rating=4)
    return HybridJobService(HybridJobRepository(session)).invalidate_recommendations(
        user.id,
        reason="collection_changed",
    )


def test_dispatcher_uploads_minimal_member_input_and_enqueues_once(session: Session) -> None:
    job = _pending_job(session)
    transport = InMemoryHybridTransport()
    dispatcher = HybridDispatcher(session, transport, catalog_version="catalog-a")

    assert dispatcher.dispatch_pending() == 1
    assert dispatcher.dispatch_pending() == 0

    session.refresh(job)
    assert job.status == "enqueued"
    assert job.input_blob == f"hybrid/jobs/{job.id}/input.json"
    payload_text = transport.blobs[job.input_blob]
    payload = json.loads(payload_text)
    assert "private@example.com" not in payload_text
    assert payload == {
        "schema_version": 1,
        "job_id": str(job.id),
        "job_type": "recommendation_bundle",
        "user_id": str(job.user_id),
        "input_version": 1,
        "catalog_version": "catalog-a",
        "collection": [
            {
                "fragrance_id": payload["collection"][0]["fragrance_id"],
                "status": "owned",
                "user_rating": 4,
            }
        ],
        "preferences": None,
    }
    assert len(transport.queues["hybrid-jobs"]) == 1


def test_worker_writes_result_and_acknowledges_job(session: Session) -> None:
    job = _pending_job(session)
    transport = InMemoryHybridTransport()
    HybridDispatcher(session, transport, catalog_version="catalog-a").dispatch_pending()

    worker = HybridWorker(
        transport,
        processor=lambda request: {
            "discovery": [],
            "layering": {"safe": [], "contrast": [], "experimental": []},
        },
        algorithm_version="1",
    )

    assert worker.process_next() is True
    assert transport.queues["hybrid-jobs"] == []
    assert len(transport.queues["hybrid-results"]) == 1
    assert f"hybrid/jobs/{job.id}/result.json" in transport.blobs


def test_worker_moves_malformed_input_to_poison_after_five_deliveries() -> None:
    transport = InMemoryHybridTransport()
    transport.upload_json("hybrid/jobs/bad/input.json", {"schema_version": 99})
    transport.enqueue(
        "hybrid-jobs",
        {
            "job_id": "00000000-0000-4000-8000-000000000001",
            "input_blob": "hybrid/jobs/bad/input.json",
        },
    )
    worker = HybridWorker(transport, processor=lambda _: {}, algorithm_version="1")

    for _ in range(4):
        assert worker.process_next() is False
        assert len(transport.queues["hybrid-jobs"]) == 1
    assert worker.process_next() is False

    assert transport.queues["hybrid-jobs"] == []
    assert len(transport.queues["hybrid-jobs-poison"]) == 1
    poison = json.loads(transport.queues["hybrid-jobs-poison"][0].body)
    assert poison["error_code"] == "invalid_job_input"
    assert "schema_version" not in poison


def test_result_applier_promotes_once_and_acknowledges_duplicates(session: Session) -> None:
    job = _pending_job(session)
    transport = InMemoryHybridTransport()
    HybridDispatcher(session, transport, catalog_version="catalog-a").dispatch_pending()
    worker = HybridWorker(
        transport,
        processor=lambda _: {"discovery": [], "layering": {}},
        algorithm_version="1",
    )
    worker.process_next()
    duplicate = transport.queues["hybrid-results"][0].body
    transport.queues["hybrid-results"].append(transport.message(duplicate))
    applier = HybridResultApplier(session, transport)

    assert applier.apply_next() is True
    assert applier.apply_next() is True

    snapshots = session.query(RecommendationSnapshot).all()
    assert len(snapshots) == 1
    assert snapshots[0].source_job_id == job.id
    assert transport.queues["hybrid-results"] == []


def test_azure_transport_round_trips_json_through_injected_clients() -> None:
    class Download:
        def __init__(self, data: str) -> None:
            self._data = data

        def readall(self) -> bytes:
            return self._data.encode()

    class BlobClient:
        def __init__(self, blobs: dict[str, str], path: str) -> None:
            self._blobs = blobs
            self._path = path

        def upload_blob(self, data: str, **_: object) -> None:
            self._blobs[self._path] = data

        def download_blob(self) -> Download:
            return Download(self._blobs[self._path])

    class ContainerClient:
        def __init__(self) -> None:
            self.blobs: dict[str, str] = {}

        def get_blob_client(self, path: str) -> BlobClient:
            return BlobClient(self.blobs, path)

    class QueueMessage:
        id = "message-1"
        pop_receipt = "receipt-1"
        dequeue_count = 1

        def __init__(self, content: str) -> None:
            self.content = content

    class QueueClient:
        def __init__(self) -> None:
            self.messages: list[QueueMessage] = []
            self.visibility_timeout: int | None = None

        def send_message(self, body: str) -> None:
            self.messages.append(QueueMessage(body))

        def receive_messages(self, **_: object) -> list[QueueMessage]:
            return self.messages[:1]

        def delete_message(self, _: str, __: str) -> None:
            self.messages.pop(0)

        def update_message(self, _: str, __: str, *, visibility_timeout: int) -> QueueMessage:
            self.visibility_timeout = visibility_timeout
            return self.messages[0]

    container = ContainerClient()
    queues: dict[str, QueueClient] = {}
    transport = AzureHybridTransport(
        container_client=container,
        queue_client_factory=lambda name: queues.setdefault(name, QueueClient()),
    )

    transport.upload_json("path/input.json", {"value": 7})
    transport.enqueue("jobs", {"blob": "path/input.json"})
    message = transport.receive("jobs")

    assert transport.download_json("path/input.json") == {"value": 7}
    assert message is not None
    assert json.loads(message.body) == {"blob": "path/input.json"}
    transport.renew("jobs", message, visibility_timeout=120)
    assert queues["jobs"].visibility_timeout == 120
    transport.delete("jobs", message)
    assert queues["jobs"].messages == []


def test_recommendation_processor_always_returns_the_versioned_bundle_shape() -> None:
    request = RecommendationJobInput(
        job_id="00000000-0000-4000-8000-000000000001",
        user_id="00000000-0000-4000-8000-000000000002",
        input_version=1,
        catalog_version="catalog-a",
        collection=[],
    )

    assert process_recommendation(request) == {
        "discovery": [],
        "layering": {"safe": [], "contrast": [], "experimental": []},
    }
