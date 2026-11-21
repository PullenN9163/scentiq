from uuid import uuid4

from scentiq_api.api.v1 import wear_recommendations as router


def test_a_recommendation_action_makes_earlier_week_entries_unreachable() -> None:
    user = uuid4()
    before = router._epoch(user)
    router._bump_epoch(user)
    assert router._epoch(user) == before + 1


def test_epochs_are_per_member() -> None:
    first, second = uuid4(), uuid4()
    router._bump_epoch(first)
    assert router._epoch(second) == 0
