from datetime import UTC, datetime
from typing import Any

from domain_fixtures import make_brand, make_collection_item, make_fragrance, make_user
from sqlalchemy.orm import Session

from scentiq_api.models import Fragrance, User, UserPreference
from scentiq_api.services.wear_recommendations import WearRecommendationService

NOW = datetime(2026, 10, 20, 23, tzinfo=UTC)


def setup_collection(session: Session) -> tuple[User, list[Fragrance]]:
    user = make_user(session, email="personalized@example.test")
    brand = make_brand(session, name="Personalized")
    fragrances = [
        make_fragrance(session, brand=brand, name=name) for name in ("Alpha", "Beta", "Gamma")
    ]
    for fragrance in fragrances:
        make_collection_item(session, user=user, fragrance=fragrance)
    return user, fragrances


def test_today_uses_current_daypart_and_explicit_taste(session: Session) -> None:
    user, fragrances = setup_collection(session)
    fragrances[1].olfactory_family = "woody"
    session.add(UserPreference(user_id=user.id, timezone="UTC", liked_families=["woody"]))
    session.flush()
    recommendation = (
        WearRecommendationService(session, clock=lambda: NOW).today(user.id).recommendations[0]
    )
    assert recommendation.context.daypart == "night"
    assert recommendation.fragrance.id == fragrances[1].id


def test_week_varies_planned_choices_and_preserves_accepted(session: Session) -> None:
    from scentiq_api.schemas.wear_recommendations import RecommendationDecisionRequest

    user, _ = setup_collection(session)
    service = WearRecommendationService(session, clock=lambda: NOW)
    plan = service.week(user.id)
    assert len({row.fragrance.id for row in plan.recommendations[:3]}) == 3
    locked = plan.recommendations[1]
    service.decide(user.id, locked.id, RecommendationDecisionRequest(action="accepted"))
    session.flush()
    assert service.week(user.id).recommendations[1].fragrance.id == locked.fragrance.id


def test_explicit_exclusions_apply_and_all_candidates_are_persisted(session: Session) -> None:
    user, fragrances = setup_collection(session)
    session.add(UserPreference(user_id=user.id, excluded_fragrance_ids=[str(fragrances[0].id)]))
    session.flush()
    result = WearRecommendationService(session, clock=lambda: NOW).today(user.id).recommendations[0]
    assert fragrances[0].id not in {item.fragrance.id for item in [result, *result.alternatives]}


def test_discovery_uses_explicit_taste_instead_of_ownership_only(session: Session) -> None:
    from scentiq_api.repositories import DiscoveryRepository
    from scentiq_api.services.discovery import DiscoveryService

    user, _fragrances = setup_collection(session)
    brand = make_brand(session, name="Discovery taste")
    liked = make_fragrance(session, brand=brand, name="Woody discovery")
    liked.olfactory_family = "woody"
    disliked = make_fragrance(session, brand=brand, name="Floral discovery")
    disliked.olfactory_family = "floral"
    session.add(
        UserPreference(user_id=user.id, liked_families=["woody"], disliked_families=["floral"])
    )
    session.flush()
    results = DiscoveryService(DiscoveryRepository(session)).discover(user.id)
    assert results[0].fragrance.id == liked.id
    assert results[0].score > next(row.score for row in results if row.fragrance.id == disliked.id)


def test_layering_excludes_disliked_fragrances(session: Session) -> None:
    from scentiq_api.repositories import LayeringRepository
    from scentiq_api.services.layering import LayeringService

    user, fragrances = setup_collection(session)
    session.add(UserPreference(user_id=user.id, excluded_fragrance_ids=[str(fragrances[0].id)]))
    session.flush()
    suggestions = LayeringService(LayeringRepository(session)).stack_suggestions(user.id)
    assert suggestions
    assert all(
        item.fragrance.id != fragrances[0].id for stack in suggestions for item in stack.items
    )


def test_advisor_another_option_advances_shared_today_selection(session: Session) -> None:
    import asyncio

    from scentiq_api.agent.tools import AgentTools
    from scentiq_api.schemas.agent import AgentChatRequest
    from scentiq_api.services.agent import AgentService

    user, _ = setup_collection(session)
    before = WearRecommendationService(session).today(user.id).recommendations[0]

    async def collect() -> list[dict[str, Any]]:
        return [
            event
            async for event in AgentService(AgentTools(session, user.id), None).chat(
                AgentChatRequest(message="Give me another option")
            )
        ]

    events = asyncio.run(collect())
    cards = [event["card"] for event in events if event["type"] == "card"]
    assert cards
    assert cards[0]["data"]["fragrance"]["id"] != str(before.fragrance.id)
    after = WearRecommendationService(session).today(user.id).recommendations[0]
    assert str(after.fragrance.id) == cards[0]["data"]["fragrance"]["id"]


def test_too_strong_feedback_reduces_sprays_without_disliking_scent(session: Session) -> None:
    from scentiq_api.schemas.wear_recommendations import RecommendationFeedbackRequest
    from scentiq_api.services.recommendation_choices import RecommendationChoiceService
    from scentiq_api.services.taste_profile import TasteProfileService

    user, _ = setup_collection(session)
    service = WearRecommendationService(session, clock=lambda: NOW)
    before = service.today(user.id).recommendations[0]
    RecommendationChoiceService(session).feedback(
        user.id,
        before.id,
        RecommendationFeedbackRequest(fragrance_id=before.fragrance.id, reason="too_strong"),
    )
    after = service.today(user.id).recommendations[0]
    same = next(
        row for row in [after, *after.alternatives] if row.fragrance.id == before.fragrance.id
    )
    assert same.recommended_sprays < before.recommended_sprays
    assert before.fragrance.id not in TasteProfileService(session).for_user(user.id).excluded_ids


def test_advisor_another_discovery_advances_shared_batch(session: Session) -> None:
    import asyncio
    from uuid import uuid4

    from scentiq_api.agent.tools import AgentTools
    from scentiq_api.schemas.agent import AgentChatRequest
    from scentiq_api.schemas.surface_choices import SurfaceChoiceRequest
    from scentiq_api.services.agent import AgentService
    from scentiq_api.services.surface_choices import SurfaceChoiceService

    user, _ = setup_collection(session)
    brand = make_brand(session, name="New discoveries")
    for index in range(4):
        make_fragrance(session, brand=brand, name=f"Discovery {index}")
    service = SurfaceChoiceService(session)
    before = service.choose(
        user.id, "discovery", SurfaceChoiceRequest(idempotency_key=uuid4(), advance=False)
    )

    async def collect() -> list[dict[str, Any]]:
        return [
            event
            async for event in AgentService(AgentTools(session, user.id), None).chat(
                AgentChatRequest(message="Give me another discovery")
            )
        ]

    events = asyncio.run(collect())
    card = next(event["card"] for event in events if event["type"] == "card")
    after = service.choose(
        user.id, "discovery", SurfaceChoiceRequest(idempotency_key=uuid4(), advance=False)
    )
    assert after.candidate_id != before.candidate_id
    assert card["data"][0]["fragrance"]["id"] == after.candidate_id
