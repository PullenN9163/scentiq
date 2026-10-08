from decimal import Decimal

import pytest
from domain_fixtures import make_brand, make_collection_item, make_fragrance, make_user
from sqlalchemy.orm import Session

from scentiq_api.errors import ApiError
from scentiq_api.models import Accord, Fragrance, FragranceAccord, User, UserPreference
from scentiq_api.repositories.layering import LayeringRepository
from scentiq_api.services.layering import LayeringService


def scents(session: Session) -> tuple[User, list[Fragrance]]:
    user = make_user(session, email="layer@example.test")
    brand = make_brand(session, name="Layer House")
    items = [
        make_fragrance(session, brand=brand, name=name, seasons=("summer",))
        for name in ("Anchor", "Fresh bridge", "Warm accent", "Bare custom")
    ]
    for slug, indices in (("woody", (0, 1, 2)), ("citrus", (1,)), ("amber", (2,))):
        accord = Accord(name=slug, slug=slug)
        session.add(accord)
        session.flush()
        for index in indices:
            session.add(
                FragranceAccord(
                    fragrance_id=items[index].id, accord_id=accord.id, weight=Decimal("0.8")
                )
            )
    for item in items:
        make_collection_item(session, user=user, fragrance=item)
        item.projection_level = "moderate"
        item.longevity_score = Decimal("6")
    items[-1].projection_level = None
    items[-1].longevity_score = None
    items[-1].seasons = []
    session.flush()
    session.expire_all()
    return user, items


def test_anchor_suggestions_and_goals_rank_useful_owned_support(session: Session) -> None:
    user, items = scents(session)
    service = LayeringService(LayeringRepository(session))
    fresh = service.stack_suggestions(user.id, anchor_id=items[0].id, goal="fresher")
    warm = service.stack_suggestions(user.id, anchor_id=items[0].id, goal="warmer")
    fresh_pairs = [stack for stack in fresh if len(stack.items) == 2]
    warm_pairs = [stack for stack in warm if len(stack.items) == 2]
    assert fresh_pairs[0].items[1].fragrance.id == items[1].id
    assert warm_pairs[0].items[1].fragrance.id == items[2].id
    assert all(stack.items[0].fragrance.id == items[0].id for stack in fresh)
    assert any(len(stack.items) == 3 for stack in fresh)


def test_stack_whole_structure_sprays_weak_evidence_and_duplicates(session: Session) -> None:
    user, items = scents(session)
    service = LayeringService(LayeringRepository(session))
    stack = service.evaluate_stack(user.id, [item.id for item in items[:3]])
    assert {item.role for item in stack.items} == {"anchor", "bridge", "accent"}
    assert sorted(item.application_order for item in stack.items) == [1, 2, 3]
    assert sum(item.suggested_sprays for item in stack.items) == stack.total_sprays
    assert stack.total_sprays <= 6
    assert 0 <= stack.score <= 1
    weak = service.evaluate_stack(user.id, [items[0].id, items[3].id])
    assert weak.evidence_coverage < stack.evidence_coverage
    assert any("evidence" in warning.lower() for warning in weak.warnings)
    with pytest.raises(ApiError):
        service.evaluate_stack(user.id, [items[0].id, items[0].id])


def test_three_strong_scents_get_overload_penalty(session: Session) -> None:
    user, items = scents(session)
    service = LayeringService(LayeringRepository(session))
    moderate = service.evaluate_stack(user.id, [item.id for item in items[:3]])
    for item in items[:3]:
        item.projection_level = "strong"
    session.flush()
    strong = service.evaluate_stack(user.id, [item.id for item in items[:3]])
    assert strong.score_components.overload_penalty > moderate.score_components.overload_penalty
    assert strong.score < moderate.score
    assert strong.warnings


def test_save_wear_rate_rename_delete_is_user_isolated(session: Session) -> None:
    user, items = scents(session)
    other = make_user(session, email="other-layer@example.test")
    service = LayeringService(LayeringRepository(session))
    saved = service.save_stack(user.id, [items[0].id, items[1].id], name="Summer")
    assert saved.name == "Summer"
    with pytest.raises(ApiError):
        service.rename_stack(other.id, saved.id, "Stolen")
    with pytest.raises(ApiError):
        service.evaluate_stack(other.id, [items[0].id, items[1].id])
    worn = service.log_stack_wear(user.id, saved.id, rating=5, notes="A bright day")
    assert worn.rating == 5
    assert service.history(user.id, saved.id)[0].notes == "A bright day"
    assert service.saved_stacks(user.id)[0].average_rating == 5
    before = service.evaluate_stack(user.id, [items[0].id, items[1].id])
    service.rate_stack_wear(user.id, saved.id, worn.id, rating=1)
    after = service.evaluate_stack(user.id, [items[0].id, items[1].id])
    assert 0 < before.score - after.score <= 0.1
    assert service.rename_stack(user.id, saved.id, "Renamed").name == "Renamed"
    service.delete_stack(user.id, saved.id)
    assert service.saved_stacks(user.id) == []


def test_small_spray_budget_never_silently_increases_user_ceiling(session: Session) -> None:
    user, items = scents(session)
    session.add(UserPreference(user_id=user.id, maximum_sprays=2))
    session.flush()
    service = LayeringService(LayeringRepository(session))
    suggestions = service.stack_suggestions(user.id, anchor_id=items[0].id)
    assert all(len(stack.items) == 2 and stack.total_sprays <= 2 for stack in suggestions)
    with pytest.raises(ApiError) as error:
        service.evaluate_stack(user.id, [item.id for item in items[:3]])
    assert error.value.code == "spray_budget_too_low"
    preference = session.get(UserPreference, user.id)
    assert preference is not None
    preference.maximum_sprays = 1
    session.flush()
    assert service.stack_suggestions(user.id, anchor_id=items[0].id) == []


def test_saved_stack_keeps_original_scoring_version_and_snapshot(session: Session) -> None:
    from scentiq_api.models.layer_stacks import LayerStack

    user, items = scents(session)
    service = LayeringService(LayeringRepository(session))
    saved = service.save_stack(user.id, [items[0].id, items[1].id], name="Snapshot")
    stored = session.get(LayerStack, saved.id)
    assert stored is not None
    assert stored.algorithm_version == "layering-v2"
    assert float(stored.score_snapshot) == saved.suggestion.score
    assert stored.score_components["overload_penalty"] == 0
    assert float(stored.evidence_coverage) == saved.suggestion.evidence_coverage


def test_saved_history_stays_visible_after_lowering_spray_ceiling(session: Session) -> None:
    user, items = scents(session)
    service = LayeringService(LayeringRepository(session))
    saved = service.save_stack(user.id, [items[0].id, items[1].id], name="Keep history")
    service.log_stack_wear(user.id, saved.id, rating=4)
    session.add(UserPreference(user_id=user.id, maximum_sprays=1))
    session.flush()
    listing = service.saved_stacks(user.id)
    assert listing[0].wear_count == 1
    assert any("ceiling" in warning for warning in listing[0].suggestion.warnings)


def test_requested_triples_are_filtered_before_small_result_limit(session: Session) -> None:
    user = make_user(session, email="triple-limit@example.test")
    brand = make_brand(session, name="Triple limit")
    for index in range(10):
        fragrance = make_fragrance(session, brand=brand, name=f"Bare fragrance {index}")
        make_collection_item(session, user=user, fragrance=fragrance)
    result = LayeringService(LayeringRepository(session)).stack_suggestions(
        user.id, stack_size=3, limit=1
    )
    assert len(result) == 1
    assert len(result[0].items) == 3
