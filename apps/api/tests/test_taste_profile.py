from layering_helpers import scents
from sqlalchemy.orm import Session

from scentiq_api.schemas.events import InteractionEventBatch, InteractionEventIn
from scentiq_api.services.events import EventService
from scentiq_api.services.taste_profile import (
    TasteProfileService,
    exploration_bonus,
    taste_affinity,
    update_affinities,
    update_component_weights,
)


def test_positive_and_negative_events_move_affinity_in_opposite_directions() -> None:
    liked = update_affinities({}, [{"vanilla": 1.0}], 1.0)
    disliked = update_affinities({}, [{"vanilla": 1.0}], -1.0)
    assert (
        taste_affinity(liked, {"vanilla": 1.0}) > 0.5 > taste_affinity(disliked, {"vanilla": 1.0})
    )
    assert taste_affinity({}, {"vanilla": 1.0}) == 0.5


def test_affinities_decay_and_stay_bounded() -> None:
    state: dict[str, float] = {}
    for _ in range(100):
        state = update_affinities(state, [{"oud": 1.0}], 1.0)
    assert state["oud"] <= 1.0
    for _ in range(200):
        state = update_affinities(state, [], 0)
    assert "oud" not in state


def test_component_weights_rise_for_components_that_predict_acceptance() -> None:
    weights: dict[str, float] = {}
    for _ in range(40):
        weights = update_component_weights(weights, {"weather": 0.9, "rotation": 0.1}, True)
    assert weights["weather"] > weights["rotation"] >= 1.0
    for _ in range(80):
        weights = update_component_weights(weights, {"weather": 0.9, "rotation": 0.1}, False)
    assert 0.5 <= weights["weather"] <= 1.8


def test_exploration_bonus_favours_under_shown_items() -> None:
    assert exploration_bonus(0, 50) > exploration_bonus(30, 50) >= 0
    assert exploration_bonus(0, 0) == 0


def test_recording_events_learns_only_from_owned_fragrances(session: Session) -> None:
    user, items = scents(session)
    service = EventService(session)
    result = service.record(
        user.id,
        InteractionEventBatch(
            events=[
                InteractionEventIn(event_type="accept", fragrance_ids=[items[0].id]),
                InteractionEventIn(event_type="filter_select", subject_type="ui"),
            ]
        ),
    )
    assert result.recorded == 2 and result.learned == 1
    assert TasteProfileService(session).affinities(user.id).get("woody", 0) > 0
