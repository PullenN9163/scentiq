"""Scheduled cleanup for accounts whose provider deletion webhook never arrived.

Run on a schedule:

    uv run --directory apps/api python -m scentiq_api.reconcile_deletions

Prints a JSON summary. `--dry-run` reports what would be removed without
touching anything, and `--grace-hours` overrides the default wait.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from scentiq_api.config import Settings
from scentiq_api.database import create_database_engine
from scentiq_api.repositories import IdentityRepository
from scentiq_api.services import RECONCILIATION_GRACE, IdentityEventService


def _parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Purge deletion-pending users whose webhook cleanup did not complete",
    )
    parser.add_argument(
        "--grace-hours",
        type=int,
        default=int(RECONCILIATION_GRACE.total_seconds() // 3600),
        help="How long a pending account waits before it is purged",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report the affected accounts without deleting them",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    arguments = _parse_arguments(argv)
    if arguments.grace_hours < 0:
        raise SystemExit("--grace-hours must not be negative")

    grace = timedelta(hours=arguments.grace_hours)
    now = datetime.now(UTC)

    engine = create_database_engine(Settings().database_url_value)
    try:
        with Session(engine) as session:
            identities = IdentityRepository(session)
            if arguments.dry_run:
                stale = identities.list_stale_deletion_pending(now - grace)
                # Only ids are printed; no email or other personal data.
                summary = {
                    "dry_run": True,
                    "grace_hours": arguments.grace_hours,
                    "pending_count": len(stale),
                    "user_ids": sorted(str(user.id) for user in stale),
                }
            else:
                purged = IdentityEventService(identities).reconcile(now=now, grace=grace)
                session.commit()
                summary = {
                    "dry_run": False,
                    "grace_hours": arguments.grace_hours,
                    "purged_count": len(purged),
                    "user_ids": sorted(str(user_id) for user_id in purged),
                }
    finally:
        engine.dispose()

    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
