"""Forty deterministic acceptance scenarios for contextual personal taste."""

from datetime import UTC, datetime

import pytest
from domain_fixtures import make_brand, make_collection_item, make_fragrance, make_user
from sqlalchemy.orm import Session

from scentiq_api.models import UserPreference
from scentiq_api.services.wear_recommendations import WearRecommendationService


@pytest.mark.parametrize("month", [1, 4, 7, 10], ids=["winter", "spring", "summer", "fall"])
@pytest.mark.parametrize("hour", [9, 21], ids=["day", "night"])
@pytest.mark.parametrize("family", ["woody", "citrus", "floral", "amber", "aromatic"])
def test_explicit_taste_remains_personal_across_seasons_and_dayparts(
    session: Session, month: int, hour: int, family: str
) -> None:
    user = make_user(session, email="scenario@example.test")
    brand = make_brand(session, name="Scenario")
    favorite = make_fragrance(session, brand=brand, name="Personal favorite")
    favorite.olfactory_family = family
    other = make_fragrance(session, brand=brand, name="Alphabetical default")
    other.olfactory_family = "other"
    for fragrance in (favorite, other):
        make_collection_item(session, user=user, fragrance=fragrance)
    session.add(
        UserPreference(user_id=user.id, timezone="UTC", liked_families=[family], maximum_sprays=2)
    )
    session.flush()
    now = datetime(2026, month, 20, hour, tzinfo=UTC)
    result = WearRecommendationService(session, clock=lambda: now).today(user.id).recommendations[0]
    assert result.fragrance.id == favorite.id
    assert result.context.daypart == ("day" if hour == 9 else "night")
    assert result.recommended_sprays <= 2
    assert 0 <= result.score <= 100
    assert result.profile_version
