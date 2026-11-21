from layering_helpers import scents
from sqlalchemy.orm import Session

from scentiq_api.repositories.layering import LayeringRepository
from scentiq_api.services.layering import LayeringService
from scentiq_api.services.layering_composition import allocate_sprays, assign_zones
from scentiq_api.services.layering_pairings import (
    known_pair_prior,
    known_pairing_score,
    rule_prior,
    shrink_prior,
)


def test_reported_pair_matches_in_either_order() -> None:
    pair = known_pair_prior("Prada Amber Pour Homme", "Avon Black Suede")
    assert pair is not None and pair.confidence == "reported"


def test_signal_rules_reward_pairs_and_penalise_clashes() -> None:
    good, rule = rule_prior({"vetiver": 0.9}, {"cedar": 0.8})
    assert rule is not None and good > 0.7
    bad, clash = rule_prior({"citrus": 0.9}, {"gourmand": 0.9})
    assert clash is not None and bad < 0.5
    neutral, none = rule_prior({"citrus": 0.05}, {"gourmand": 0.05})
    assert none is None and neutral == 0.5


def test_pairing_score_reports_evidence_and_neutral_when_unknown() -> None:
    score, evidence, confidence = known_pairing_score(
        ["a x", "b y"], [{"vanilla": 0.9}, {"amber": 0.8}]
    )
    assert score > 0.7 and evidence and confidence == "heuristic"
    assert known_pairing_score(["a", "b"], [{"foo": 1.0}, {"bar": 1.0}]) == (0.5, [], None)


def test_user_ratings_pull_prior_toward_taste() -> None:
    assert shrink_prior(0.8, "heuristic", []) == 0.8
    assert shrink_prior(0.8, "heuristic", [1, 1, 1, 1]) < 0.5
    assert shrink_prior(0.4, "reported", [5, 5]) > 0.6


def test_spray_allocation_favours_filtered_scent_and_zones_are_distinct() -> None:
    sprays = allocate_sprays(3, 5, anchor_index=0, favored_index=2, bridge_index=1)
    assert sum(sprays) == 5 and sprays[2] == 3
    zones = assign_zones([2, 1, 1], [0.9, 0.5, 0.3])
    used = [entry.zone for item in zones for entry in item]
    assert len(used) == len(set(used))
    assert zones[0][0].zone in ("chest", "back_of_neck")


def test_blend_has_percent_zones_and_filters_change_composition(session: Session) -> None:
    user, items = scents(session)
    service = LayeringService(LayeringRepository(session))
    plain = service.evaluate_stack(user.id, [items[0].id, items[1].id, items[2].id])
    assert plain.score_percent == round(plain.score * 100)
    assert all(item.zones for item in plain.items)
    assert sum(z.sprays for item in plain.items for z in item.zones) == plain.total_sprays
    warm = service.evaluate_stack(user.id, [items[0].id, items[1].id, items[2].id], goal="warmer")
    soft = service.evaluate_stack(user.id, [items[0].id, items[1].id, items[2].id], goal="softer")
    assert warm.filter_effects and soft.total_sprays <= 3
    by_id = {item.fragrance.id: item.suggested_sprays for item in warm.items}
    assert by_id[items[2].id] >= by_id[items[1].id]
    safe = service.stack_suggestions(user.id, anchor_id=items[0].id, mode="safe")
    assert all(stack.total_sprays <= 4 for stack in safe)


def test_surprise_me_varies_by_seed_but_repeats_for_same_seed(session: Session) -> None:
    user, _ = scents(session)
    service = LayeringService(LayeringRepository(session))
    runs = {
        tuple(
            i.fragrance.id for i in service.stack_suggestions(user.id, surprise_seed=seed)[0].items
        )
        for seed in range(12)
    }
    assert len(runs) > 1
    first = service.stack_suggestions(user.id, surprise_seed=3)[0]
    again = service.stack_suggestions(user.id, surprise_seed=3)[0]
    assert [i.fragrance.id for i in first.items] == [i.fragrance.id for i in again.items]
