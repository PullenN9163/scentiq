"""How many database round trips Today's plan and the week plan make.

Every round trip costs real time on the live system (the database is a region away), so the
plan generators are held to a statement budget. The counts come from a realistic collection:
twenty-five owned fragrances with accords, seasons and occasions, plus wear history.
"""

import re
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

from domain_fixtures import make_brand, make_collection_item, make_fragrance, make_user, make_wear
from sqlalchemy import event
from sqlalchemy.orm import Session

from scentiq_api.models import UserPreference
from scentiq_api.services.wear_recommendations import WearRecommendationService

NOW = datetime(2026, 11, 20, 9, 30, tzinfo=UTC)


def _build_member(session: Session) -> object:
    user = make_user(session, email="budget@example.test")
    brand = make_brand(session, name="Budget House")
    items = []
    for index in range(25):
        fragrance = make_fragrance(
            session,
            brand=brand,
            name=f"Scent {index:02d}",
            accords=("woody", "fresh", "amber"),
            seasons=("fall", "winter") if index % 2 else ("spring", "summer"),
            occasions=("work", "casual"),
        )
        fragrance.olfactory_family = ("woody", "citrus", "floral", "amber", "aromatic")[index % 5]
        items.append(
            make_collection_item(session, user=user, fragrance=fragrance, user_rating=3 + index % 3)
        )
    for index, item in enumerate(items[:8]):
        make_wear(session, user=user, item=item, days_ago=2 + index * 3)
    session.add(UserPreference(user_id=user.id, timezone="UTC", maximum_sprays=3))
    session.flush()
    session.commit()
    return user


@contextmanager
def count_statements(session: Session) -> Iterator[Counter[str]]:
    counts: Counter[str] = Counter()
    engine = session.get_bind()

    def record(_conn: object, _cursor: object, statement: str, *_rest: object) -> None:
        match = re.search(r"\b(?:FROM|INTO|UPDATE)\s+\"?(\w+)\"?", statement, re.IGNORECASE)
        label = (statement.split()[0].upper() + " " + (match.group(1) if match else "")).strip()
        counts[label] += 1

    event.listen(engine, "before_cursor_execute", record)
    try:
        yield counts
    finally:
        event.remove(engine, "before_cursor_execute", record)


def _report(title: str, counts: Counter[str]) -> None:
    total = sum(counts.values())
    top = ", ".join(f"{name} x{n}" for name, n in counts.most_common(8))
    print(f"\n{title}: {total} statements; most frequent: {top}")


def test_today_and_week_plans_stay_within_a_statement_budget(session: Session) -> None:
    user = _build_member(session)
    service = WearRecommendationService(session, clock=lambda: NOW)

    with count_statements(session) as today_counts:
        service.today(user.id)  # type: ignore[attr-defined]
        session.commit()
    _report("today (first generation)", today_counts)

    with count_statements(session) as repeat_counts:
        WearRecommendationService(session, clock=lambda: NOW).today(user.id)  # type: ignore[attr-defined]
        session.commit()
    _report("today (repeat, reused)", repeat_counts)

    with count_statements(session) as week_counts:
        WearRecommendationService(session, clock=lambda: NOW).week(user.id)  # type: ignore[attr-defined]
        session.commit()
    _report("week (first generation)", week_counts)

    with count_statements(session) as week_repeat:
        WearRecommendationService(session, clock=lambda: NOW).week(user.id)  # type: ignore[attr-defined]
        session.commit()
    _report("week (repeat, reused)", week_repeat)

    # Budgets sit a little above today's measured counts (32, 25, 109 and 85). Raising one should
    # be a deliberate decision: each statement is a round trip to a database a region away.
    assert sum(today_counts.values()) <= 36
    assert sum(repeat_counts.values()) <= 29
    assert sum(week_counts.values()) <= 120
    assert sum(week_repeat.values()) <= 95
