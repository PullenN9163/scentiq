from __future__ import annotations

import argparse
import json
import time
from collections.abc import Sequence

from scentiq_api.config import HybridWorkerSettings, Settings
from scentiq_api.database import create_database_engine, create_session_factory
from scentiq_api.hybrid import (
    AzureHybridTransport,
    HybridDispatcher,
    HybridPoisonApplier,
    HybridResultApplier,
    HybridWorker,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Operate ScentIQ hybrid background jobs")
    commands = parser.add_subparsers(dest="command", required=True)

    dispatch = commands.add_parser("dispatch", help="Dispatch durable pending jobs")
    dispatch.add_argument("--catalog-version", required=True)
    dispatch.add_argument("--limit", type=int, default=25)

    commands.add_parser("apply-results", help="Apply one completed job result")

    bridge = commands.add_parser("bridge", help="Dispatch jobs and apply completed results")
    bridge.add_argument("--catalog-version", required=True)
    bridge.add_argument("--dispatch-limit", type=int, default=25)
    bridge.add_argument("--result-limit", type=int, default=25)

    worker = commands.add_parser("worker", help="Process queued jobs")
    worker.add_argument("--algorithm-version", required=True)
    worker.add_argument("--once", action="store_true")
    worker.add_argument("--poll-seconds", type=float, default=5.0)
    return parser


def _transport(settings: Settings | HybridWorkerSettings) -> AzureHybridTransport:
    blob_url = settings.azure_storage_account_url
    if blob_url is None:
        raise RuntimeError("AZURE_STORAGE_ACCOUNT_URL is required for hybrid operations")
    return AzureHybridTransport.from_account_urls(
        blob_account_url=blob_url,
        queue_account_url=settings.azure_storage_queue_account_url,
    )


def _dispatch(args: argparse.Namespace, settings: Settings) -> int:
    engine = create_database_engine(settings.database_url_value)
    factory = create_session_factory(engine)
    try:
        with factory() as session:
            count = HybridDispatcher(
                session,
                _transport(settings),
                catalog_version=args.catalog_version,
            ).dispatch_pending(limit=args.limit)
            session.commit()
            print(json.dumps({"dispatched": count}))
    finally:
        engine.dispose()
    return 0


def _apply_result(settings: Settings) -> int:
    engine = create_database_engine(settings.database_url_value)
    factory = create_session_factory(engine)
    try:
        with factory() as session:
            applied = HybridResultApplier(session, _transport(settings)).apply_next()
            session.commit()
            print(json.dumps({"applied": applied}))
    finally:
        engine.dispose()
    return 0


def _bridge(args: argparse.Namespace, settings: Settings) -> int:
    engine = create_database_engine(settings.database_url_value)
    factory = create_session_factory(engine)
    transport = _transport(settings)
    try:
        with factory() as session:
            dispatched = HybridDispatcher(
                session,
                transport,
                catalog_version=args.catalog_version,
            ).dispatch_pending(limit=args.dispatch_limit)
            applier = HybridResultApplier(session, transport)
            poison_applier = HybridPoisonApplier(session, transport)
            applied = 0
            while applied < args.result_limit and applier.apply_next():
                applied += 1
            poisoned = 0
            while poisoned < args.result_limit and poison_applier.apply_next():
                poisoned += 1
            session.commit()
            print(json.dumps({"applied": applied, "dispatched": dispatched, "poisoned": poisoned}))
    finally:
        engine.dispose()
    return 0


def _worker(args: argparse.Namespace, settings: HybridWorkerSettings) -> int:
    from scentiq_api.hybrid.processor import process_recommendation

    worker = HybridWorker(
        _transport(settings),
        processor=process_recommendation,
        algorithm_version=args.algorithm_version,
    )
    while True:
        processed = worker.process_next()
        if args.once:
            print(json.dumps({"processed": processed}))
            return 0
        if not processed:
            time.sleep(args.poll_seconds)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "dispatch":
        return _dispatch(args, Settings())
    if args.command == "apply-results":
        return _apply_result(Settings())
    if args.command == "bridge":
        return _bridge(args, Settings())
    if args.command == "worker":
        return _worker(args, HybridWorkerSettings())
    raise AssertionError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
