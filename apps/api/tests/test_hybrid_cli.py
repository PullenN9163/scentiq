from typing import Any

from pytest import MonkeyPatch

from scentiq_api.hybrid import AzureHybridTransport, InMemoryHybridTransport
from scentiq_api.hybrid.__main__ import build_parser, main


def test_hybrid_cli_exposes_operational_commands() -> None:
    parser = build_parser()

    assert parser.parse_args(["dispatch", "--catalog-version", "catalog-a"]).command == "dispatch"
    assert parser.parse_args(["apply-results"]).command == "apply-results"
    bridge = parser.parse_args(["bridge", "--catalog-version", "catalog-a"])
    assert bridge.command == "bridge"
    assert bridge.result_limit == 25
    worker = parser.parse_args(["worker", "--once", "--algorithm-version", "1"])
    assert worker.command == "worker"
    assert worker.once is True


def test_worker_starts_without_api_database_or_cors_settings(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("SCENTIQ_ENV", "production")
    monkeypatch.setenv(
        "AZURE_STORAGE_ACCOUNT_URL",
        "https://example.blob.core.windows.net/",
    )
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    transport = InMemoryHybridTransport()

    def create_transport(cls: type[AzureHybridTransport], **kwargs: Any) -> InMemoryHybridTransport:
        del cls, kwargs
        return transport

    monkeypatch.setattr(AzureHybridTransport, "from_account_urls", classmethod(create_transport))

    assert main(["worker", "--once", "--algorithm-version", "v1"]) == 0
