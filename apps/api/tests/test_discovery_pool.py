"""Pool-served filtered Discover must match the live path exactly, or fall back."""

from __future__ import annotations

import functools
import json
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from domain_fixtures import make_brand, make_collection_item, make_user
from sqlalchemy.orm import Session
from test_discovery_feed import _feed_client

from scentiq_api.api.v1 import discovery_feed
from scentiq_api.hybrid import processor
from scentiq_api.hybrid.contracts import RecommendationJobInput
from scentiq_api.hybrid.runtime import HybridDispatcher
from scentiq_api.hybrid.transport import InMemoryHybridTransport
from scentiq_api.models import (
    Accord,
    AsyncJob,
    Fragrance,
    FragranceAccord,
    FragranceCommunityStats,
    FragranceSeason,
    RecommendationSnapshot,
    User,
    UserPreference,
)
from scentiq_api.repositories import DiscoveryRepository, HybridJobRepository
from scentiq_api.schemas.discovery import DiscoveryResult
from scentiq_api.services import DiscoveryService, HybridJobService
from scentiq_api.services.discovery_pool import (
    DISCOVERY_POOL_DEPTH,
    PoolFilters,
    build_discovery_pool,
    pool_can_answer,
    pool_rows,
)
from scentiq_api.services.taste_profile import TasteProfileService

# name, gender, family, accords, seasons, popularity, rating_count, price value
CATALOG: list[
    tuple[str, str | None, str | None, dict[str, float], dict[str, float], int, int, str | None]
] = [
    (
        "Alpha",
        "male",
        "Woody",
        {"Woody": 0.9, "Warm Spicy": 0.6},
        {"fall": 0.9, "winter": 0.8},
        100,
        900,
        "4.50",
    ),
    (
        "Bravo",
        "female",
        "Floral",
        {"White Floral": 0.9, "Rose": 0.5},
        {"spring": 0.9},
        99,
        800,
        "3.20",
    ),
    (
        "Charlie",
        "unisex",
        "Citrus",
        {"Citrus": 0.9, "Fresh": 0.4},
        {"summer": 0.95, "spring": 0.4},
        98,
        700,
        "4.10",
    ),
    ("Delta", "male", "Aromatic", {"Aromatic": 0.8, "Woody": 0.3}, {"fall": 0.5}, 97, 600, None),
    (
        "Echo",
        "female",
        "Floral",
        {"Rose": 0.9, "Powdery": 0.5},
        {"spring": 0.7, "summer": 0.2},
        96,
        500,
        "4.80",
    ),
    ("Foxtrot", "male", "Woody", {"Woody": 0.7, "Citrus": 0.5}, {"winter": 0.9}, 95, 500, "2.00"),
    (
        "Golf",
        "unisex",
        "Oriental",
        {"Vanilla": 0.9, "Warm Spicy": 0.8},
        {"winter": 0.95, "fall": 0.6},
        94,
        400,
        "4.00",
    ),
    ("Hotel", "male", "Citrus", {"Citrus": 0.9, "Aquatic": 0.7}, {"summer": 0.9}, 93, 300, "3.90"),
    ("India", "male", "Woody", {"Woody": 0.6, "Amber": 0.9}, {"fall": 0.7}, 92, 300, "4.60"),
    (
        "Juliet",
        "male",
        "Oriental",
        {"Amber": 0.8, "Vanilla": 0.4},
        {"winter": 0.6},
        91,
        200,
        "3.00",
    ),
    ("Kilo", None, "Woody", {"Woody": 0.5}, {}, 90, 200, "4.20"),
    ("Lima", "male", None, {"Leather": 0.9}, {"fall": 0.3}, 89, 100, "4.00"),
    (
        "Mike",
        "unisex",
        "Aromatic",
        {"Aromatic": 0.5, "Fresh": 0.9},
        {"summer": 0.5},
        88,
        100,
        "1.50",
    ),
    ("Nova", "female", "Citrus", {"Citrus": 0.6}, {"summer": 0.8, "spring": 0.6}, 87, 50, "4.90"),
]
OWNED = [
    ("Own One", "male", "Woody", {"Woody": 0.9, "Amber": 0.5}, {"fall": 0.8}),
    ("Own Two", "unisex", "Citrus", {"Citrus": 0.8, "Fresh": 0.7}, {"summer": 0.8}),
]
EXCLUDED_NAME = "Echo"


class World:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.user: User = make_user(session, email=f"pool-{uuid4().hex[:8]}@example.test")
        self.brand = make_brand(session, name=f"Pool House {uuid4().hex[:6]}")
        self._accords: dict[str, Accord] = {}
        self.by_name: dict[str, Fragrance] = {}

    def _accord(self, name: str) -> Accord:
        if name not in self._accords:
            accord = Accord(name=name, slug=f"{name.lower().replace(' ', '-')}-{uuid4().hex[:6]}")
            self.session.add(accord)
            self.session.flush()
            self._accords[name] = accord
        return self._accords[name]

    def add(
        self,
        name: str,
        gender: str | None,
        family: str | None,
        accords: dict[str, float],
        seasons: dict[str, float],
        *,
        popularity: int = 0,
        rating_count: int = 0,
        price: str | None = None,
    ) -> Fragrance:
        item = Fragrance(
            brand_id=self.brand.id,
            name=name,
            concentration="edp",
            search_text=name.lower(),
            gender=gender,
            olfactory_family=family,
            popularity_score=float(popularity),
            rating_count=rating_count,
            rating_average=Decimal("4.1"),
        )
        self.session.add(item)
        self.session.flush()
        for accord_name, weight in accords.items():
            self.session.add(
                FragranceAccord(
                    fragrance_id=item.id,
                    accord_id=self._accord(accord_name).id,
                    weight=Decimal(str(weight)),
                )
            )
        for season, weight in seasons.items():
            self.session.add(
                FragranceSeason(fragrance_id=item.id, season=season, weight=Decimal(str(weight)))
            )
        if price is not None:
            self.session.add(
                FragranceCommunityStats(fragrance_id=item.id, price_value_average=Decimal(price))
            )
        self.session.flush()
        self.by_name[name] = item
        return item

    def populate(self, *, exclude_one: bool = True) -> None:
        for own_name, own_gender, own_family, own_accords, own_seasons in OWNED:
            owned = self.add(own_name, own_gender, own_family, own_accords, own_seasons)
            make_collection_item(self.session, user=self.user, fragrance=owned)
        for name, gender, family, accords, seasons, popularity, count, price in CATALOG:
            self.add(
                name,
                gender,
                family,
                accords,
                seasons,
                popularity=popularity,
                rating_count=count,
                price=price,
            )
        if exclude_one:
            self.session.add(
                UserPreference(
                    user_id=self.user.id,
                    excluded_fragrance_ids=[str(self.by_name[EXCLUDED_NAME].id)],
                )
            )
        self.session.flush()

    def job_input(self) -> RecommendationJobInput:
        job = AsyncJob(
            job_type="recommendation_bundle",
            status="pending",
            user_id=self.user.id,
            input_version=0,
            execution_id=str(uuid4()),
            idempotency_key=f"pool:{uuid4()}",
            reason="pool_test",
            schema_version=1,
            attempt_count=0,
        )
        self.session.add(job)
        self.session.flush()
        dispatcher = HybridDispatcher(
            self.session, InMemoryHybridTransport(), catalog_version="catalog-test"
        )
        return dispatcher._recommendation_input(job)

    def snapshot(self, *, with_pool: bool = True, input_version: int = 0) -> dict[str, Any]:
        request = self.job_input()
        payload: dict[str, Any] = json.loads(json.dumps(processor.process_recommendation(request)))
        payload["excluded_ids"] = [str(value) for value in request.excluded_ids]
        if not with_pool:
            payload.pop("discovery_pool")
        job = AsyncJob(
            job_type="recommendation_bundle",
            status="succeeded",
            user_id=self.user.id,
            input_version=input_version,
            idempotency_key=f"pool-snapshot:{uuid4()}",
            reason="pool_test",
            schema_version=1,
            attempt_count=0,
        )
        self.session.add(job)
        self.session.flush()
        self.session.add(
            RecommendationSnapshot(
                user_id=self.user.id,
                source_job_id=job.id,
                input_version=input_version,
                algorithm_version="algorithm-test",
                catalog_version="catalog-test",
                payload=payload,
            )
        )
        self.session.flush()
        return payload

    def live(self, *, limit: int, offset: int, mode: str, **filters: Any) -> list[dict[str, Any]]:
        rows = DiscoveryService(DiscoveryRepository(self.session)).discover(
            self.user.id,
            limit=limit,
            offset=offset,
            mode=mode,  # type: ignore[arg-type]
            rank_with_ai=False,
            **filters,
        )
        return [row.model_dump(mode="json") for row in rows]


@pytest.fixture
def world(session: Session) -> World:
    value = World(session)
    value.populate()
    return value


def _forbidden(*args: Any, **kwargs: Any) -> Any:
    raise AssertionError("the live path must not run for a pool-served request")


@pytest.fixture
def no_live(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(discovery_feed, "_live_discovery", _forbidden)


def _get(world: World, **params: Any) -> dict[str, Any]:
    with _feed_client(world.session, world.user) as client:
        response = client.get("/discovery-feed", params=params)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


FILTER_CASES: list[dict[str, Any]] = [
    {"gender": "male"},
    {"gender": "female"},
    {"gender": "unisex"},
    {"family": "woody"},
    {"family": "CITRUS"},
    {"season": "summer"},
    {"season": "winter"},
    {"accord": "warm spicy"},
    {"accord": "Citrus"},
    {"minimum_value": 4.0},
    {"minimum_value": 4.5},
    {"gender": "male", "family": "Woody"},
    {"gender": "male", "season": "fall"},
    {"family": "Citrus", "accord": "fresh"},
    {"gender": "unisex", "minimum_value": 4.0},
    {"gender": "male", "family": "Woody", "season": "fall", "accord": "amber", "minimum_value": 4},
    {"accord": "does not exist"},
    {"gender": "female", "family": "Woody"},
]


@pytest.mark.parametrize("mode", ["balance", "taste", "explore", "seasonal"])
@pytest.mark.parametrize("filters", FILTER_CASES, ids=lambda case: "&".join(sorted(case)))
@pytest.mark.parametrize(("limit", "offset"), [(3, 0), (3, 3), (50, 0)])
def test_pool_filtered_results_equal_live_results(
    world: World,
    no_live: None,
    mode: str,
    filters: dict[str, Any],
    limit: int,
    offset: int,
) -> None:
    world.snapshot()
    body = _get(world, mode=mode, limit=limit, offset=offset, **filters)
    assert body["refresh_status"] == "fresh"
    assert body["items"] == world.live(limit=limit, offset=offset, mode=mode, **filters)


def test_pool_results_are_complete_enough_to_be_meaningful(world: World) -> None:
    world.snapshot()
    assert len(world.live(limit=50, offset=0, mode="balance", gender="male")) >= 5
    assert len(world.live(limit=50, offset=0, mode="balance", season="summer")) >= 4
    assert world.live(limit=50, offset=0, mode="balance", accord="does not exist") == []
    # Ownership and exclusion are real: neither appears anywhere in the live ranking.
    names = {row["fragrance"]["name"] for row in world.live(limit=50, offset=0, mode="balance")}
    assert EXCLUDED_NAME not in names and not names & {"Own One", "Own Two"}


def test_missing_pool_falls_back_to_the_live_path(world: World) -> None:
    world.snapshot(with_pool=False)
    body = _get(world, gender="male", limit=3)
    assert body["refresh_status"] == "fallback"
    assert body["items"] == world.live(limit=3, offset=0, mode="balance", gender="male")


def test_stale_snapshot_falls_back_to_the_live_path(world: World) -> None:
    world.snapshot()
    HybridJobService(HybridJobRepository(world.session)).invalidate_recommendations(
        world.user.id, reason="collection_changed"
    )
    body = _get(world, gender="male", limit=3)
    assert body["refresh_status"] == "fallback"
    assert body["items"] == world.live(limit=3, offset=0, mode="balance", gender="male")


def test_old_snapshot_versions_never_use_the_pool(world: World) -> None:
    payload = world.snapshot()
    snapshot = world.session.query(RecommendationSnapshot).one()
    snapshot.catalog_version = "older-catalog"
    world.session.flush()
    assert payload["discovery_pool"]["lists"]
    body = _get(world, gender="male", limit=3)
    assert body["refresh_status"] == "fallback"


def test_owned_and_excluded_fragrances_never_appear(world: World) -> None:
    payload = world.snapshot()
    pooled_names = {data["f"]["name"] for data in payload["discovery_pool"]["fragrances"].values()}
    assert {"Alpha", "Bravo"} <= pooled_names
    # Changes made after the snapshot was taken: Alpha becomes owned, Bravo excluded.
    make_collection_item(world.session, user=world.user, fragrance=world.by_name["Alpha"])
    payload["excluded_ids"].append(str(world.by_name["Bravo"].id))
    snapshot = world.session.query(RecommendationSnapshot).one()
    snapshot.payload = json.loads(json.dumps(payload))
    world.session.flush()

    for params in (
        {"gender": "male"},
        {"gender": "female"},
        {"family": "floral"},
        {"season": "fall"},
    ):
        body = _get(world, limit=50, **params)
        names = {item["fragrance"]["name"] for item in body["items"]}
        assert not names & {"Alpha", "Bravo", EXCLUDED_NAME, "Own One", "Own Two"}, params


def test_private_catalog_rows_in_the_pool_are_dropped(world: World) -> None:
    payload = world.snapshot()
    delta = world.by_name["Delta"]
    delta.owner_user_id = world.user.id
    world.session.flush()
    body = _get(world, limit=50, gender="male")
    assert "Delta" not in {item["fragrance"]["name"] for item in body["items"]}
    assert payload["discovery_pool"]["universe_complete"] is True


def _shallow(monkeypatch: pytest.MonkeyPatch, depth: int) -> None:
    monkeypatch.setattr(
        processor,
        "build_discovery_pool",
        functools.partial(build_discovery_pool, depth=depth),
    )


def test_shallow_pool_answers_what_it_holds_and_falls_back_for_the_rest(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    _shallow(monkeypatch, 6)
    payload = world.snapshot()
    pool = payload["discovery_pool"]
    assert pool["depth"] == 6
    for mode in ("balance", "taste", "explore"):
        assert len(pool["lists"][mode]["rows"]) == 6 and not pool["lists"][mode]["full"]

    held = pool_rows(payload, mode="balance", season=None, filters=PoolFilters(gender="male"))
    assert held is not None
    held_count = len(held[0])
    assert 2 <= held_count < 6

    # Enough matching rows inside the pool: served from the snapshot, equal to live.
    expected = world.live(limit=held_count, offset=0, mode="balance", gender="male")
    with monkeypatch.context() as scope:
        scope.setattr(discovery_feed, "_live_discovery", _forbidden)
        body = _get(world, mode="balance", gender="male", limit=held_count)
    assert body["refresh_status"] == "fresh"
    assert body["items"] == expected

    # One more row than the pool holds for this filter: must fall back and still be exact.
    body = _get(world, mode="balance", gender="male", limit=held_count + 1)
    assert body["refresh_status"] == "fallback"
    assert body["items"] == world.live(
        limit=held_count + 1, offset=0, mode="balance", gender="male"
    )
    # A truncated pool cannot prove a short page is the whole answer.
    body = _get(world, mode="balance", family="Oriental", limit=3)
    assert body["items"] == world.live(limit=3, offset=0, mode="balance", family="Oriental")


@pytest.mark.parametrize("mode", ["balance", "seasonal"])
@pytest.mark.parametrize("depth", [2, 6])
@pytest.mark.parametrize("filters", FILTER_CASES, ids=lambda case: "&".join(sorted(case)))
def test_shallow_pool_is_always_exact_whether_or_not_it_answers(
    world: World,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    depth: int,
    filters: dict[str, Any],
) -> None:
    _shallow(monkeypatch, depth)
    world.snapshot()
    body = _get(world, mode=mode, limit=4, **filters)
    assert body["items"] == world.live(limit=4, offset=0, mode=mode, **filters)
    assert body["refresh_status"] in {"fresh", "fallback"}


def test_truncated_candidate_universe_only_answers_provably_complete_facets(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Only the eight most popular candidates are scored, as when the catalog is larger
    # than the candidate pool. Alpha..Hotel are the top eight.
    monkeypatch.setattr("scentiq_api.repositories.discovery.DISCOVERY_CANDIDATE_POOL", 8)
    monkeypatch.setattr(processor, "DISCOVERY_CANDIDATE_POOL", 8)
    world = World(session)
    world.populate()
    payload = world.snapshot()
    pool = payload["discovery_pool"]
    assert pool["universe_complete"] is False

    # A facet is complete when every catalog fragrance with that value is among the
    # eight candidates (Floral: Bravo and Echo; Rose likewise). Male, female and winter
    # each have a member beyond the top eight (Juliet, Nova, Juliet), so they are not.
    complete = pool["complete_facets"]
    assert "floral" in complete["family"]
    assert "male" not in complete["gender"]
    assert "female" not in complete["gender"]
    assert "rose" in complete["accord"]
    assert "winter" not in complete["season"]

    def served(**filters: Any) -> str:
        return str(_get(world, mode="balance", limit=3, **filters)["refresh_status"])

    for filters, expected in (
        ({"family": "floral"}, "fresh"),
        ({"accord": "rose"}, "fresh"),
        ({"gender": "female", "family": "floral"}, "fresh"),
        ({"gender": "male"}, "fallback"),
        ({"minimum_value": 4.0}, "fallback"),
        ({"season": "winter"}, "fallback"),
        ({"gender": "male", "season": "fall"}, "fallback"),
    ):
        # The live candidate query is capped the same way, so the two stay comparable.
        assert served(**filters) == expected, filters
        assert _get(world, mode="balance", limit=3, **filters)["items"] == world.live(
            limit=3, offset=0, mode="balance", **filters
        ), filters


def test_pool_can_answer_requires_a_complete_universe_or_a_complete_facet() -> None:
    base: dict[str, Any] = {
        "universe_complete": False,
        "complete_facets": {"gender": ["male"], "family": ["woody"], "season": [], "accord": []},
    }
    assert pool_can_answer({**base, "universe_complete": True}, PoolFilters(minimum_value=4))
    assert not pool_can_answer(base, PoolFilters(minimum_value=4))
    assert not pool_can_answer(base, PoolFilters(gender="female"))
    assert pool_can_answer(base, PoolFilters(gender="female", family="WOODY"))
    assert not pool_can_answer({**base, "complete_facets": None}, PoolFilters(gender="male"))


def test_pool_payload_is_additive_and_bounded(world: World) -> None:
    request = world.job_input()
    payload = processor.process_recommendation(request)
    assert set(payload) == {
        "profile_version",
        "discovery",
        "discovery_modes",
        "discovery_seasonal",
        "layering",
        "discovery_pool",
    }
    pool = payload["discovery_pool"]
    assert set(pool["lists"]) == {
        "balance",
        "taste",
        "explore",
        "seasonal:spring",
        "seasonal:summer",
        "seasonal:fall",
        "seasonal:winter",
    }
    assert pool["depth"] == DISCOVERY_POOL_DEPTH
    assert all(len(entry["rows"]) <= DISCOVERY_POOL_DEPTH for entry in pool["lists"].values())
    # The legacy keys are still the full-fidelity ranked head.
    assert [row["fragrance"]["id"] for row in payload["discovery_modes"]["balance"]] == [
        row[0] for row in pool["lists"]["balance"]["rows"]
    ]
    for rows in payload["discovery_modes"].values():
        for row in rows:
            DiscoveryResult.model_validate(row)
    assert (
        TasteProfileService(world.session).for_user(world.user.id).version
        == payload["profile_version"]
    )
