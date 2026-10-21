from uuid import uuid4

from sqlalchemy.orm import Session
from test_recommendation_choices import batch

from scentiq_api.schemas.surface_choices import SurfaceChoiceRequest
from scentiq_api.services.surface_choices import SurfaceChoiceService


def test_layering_options_are_canonical_stable_and_idempotent(session: Session) -> None:
    user, _, _ = batch(session)
    service = SurfaceChoiceService(session)
    initial = service.choose(
        user.id, "layering", SurfaceChoiceRequest(idempotency_key=uuid4(), advance=False)
    )
    assert initial.selected is not None
    request = SurfaceChoiceRequest(
        batch_id=initial.batch_id,
        idempotency_key=uuid4(),
        expected_candidate_id=initial.candidate_id,
    )
    second = service.choose(user.id, "layering", request)
    assert second.candidate_id != initial.candidate_id
    assert service.choose(user.id, "layering", request) == second
    reload = service.choose(
        user.id, "layering", SurfaceChoiceRequest(idempotency_key=uuid4(), advance=False)
    )
    assert reload.batch_id == initial.batch_id
    assert reload.candidate_id == second.candidate_id


def test_changed_collection_invalidates_surface_batch(session: Session) -> None:
    import pytest
    from sqlalchemy import select

    from scentiq_api.errors import ApiError
    from scentiq_api.models import UserCollectionItem

    user, _, _ = batch(session)
    service = SurfaceChoiceService(session)
    initial = service.choose(
        user.id, "layering", SurfaceChoiceRequest(idempotency_key=uuid4(), advance=False)
    )
    item = session.scalar(select(UserCollectionItem).where(UserCollectionItem.user_id == user.id))
    assert item is not None
    item.status = "sold"
    session.flush()
    with pytest.raises(ApiError) as error:
        service.choose(
            user.id,
            "layering",
            SurfaceChoiceRequest(batch_id=initial.batch_id, idempotency_key=uuid4()),
        )
    assert error.value.code == "batch_changed"


def test_other_member_cannot_advance_a_surface_batch(session: Session) -> None:
    import pytest
    from domain_fixtures import make_user

    from scentiq_api.errors import ApiError

    user, _, _ = batch(session)
    service = SurfaceChoiceService(session)
    initial = service.choose(
        user.id, "layering", SurfaceChoiceRequest(idempotency_key=uuid4(), advance=False)
    )
    other = make_user(session, email="foreign-surface@example.test")
    with pytest.raises(ApiError):
        service.choose(
            other.id,
            "layering",
            SurfaceChoiceRequest(batch_id=initial.batch_id, idempotency_key=uuid4()),
        )


def test_empty_surface_batch_reports_exhaustion(session: Session) -> None:
    from domain_fixtures import make_user

    user = make_user(session, email="empty-surface@example.test")
    result = SurfaceChoiceService(session).choose(
        user.id, "layering", SurfaceChoiceRequest(idempotency_key=uuid4(), advance=False)
    )
    assert result.selected is None
    assert result.options_exhausted
    assert result.remaining_options == 0


def test_layering_batch_exhausts_without_reordered_stack_repeats_and_resets(
    session: Session,
) -> None:
    user, _, _ = batch(session)
    service = SurfaceChoiceService(session)
    current = service.choose(
        user.id, "layering", SurfaceChoiceRequest(idempotency_key=uuid4(), advance=False)
    )
    initial_key = current.candidate_id
    seen = {initial_key}
    for _ in range(current.remaining_options):
        following = service.choose(
            user.id,
            "layering",
            SurfaceChoiceRequest(
                batch_id=current.batch_id,
                idempotency_key=uuid4(),
                expected_candidate_id=current.candidate_id,
            ),
        )
        assert following.candidate_id not in seen
        seen.add(following.candidate_id)
        current = following
    assert len(seen) == 4
    assert current.options_exhausted
    repeat = service.choose(
        user.id,
        "layering",
        SurfaceChoiceRequest(
            batch_id=current.batch_id,
            idempotency_key=uuid4(),
            expected_candidate_id=current.candidate_id,
        ),
    )
    assert repeat.candidate_id == current.candidate_id
    reset = service.choose(
        user.id,
        "layering",
        SurfaceChoiceRequest(batch_id=current.batch_id, idempotency_key=uuid4(), reset=True),
    )
    assert reset.candidate_id == initial_key
    assert reset.remaining_options == 3


def test_discovery_advances_to_an_unowned_fragrance(session: Session) -> None:
    from domain_fixtures import make_brand, make_fragrance

    user, _, original = batch(session, 1)
    brand = make_brand(session, name="New discoveries")
    for name in ("Discovery alpha", "Discovery beta"):
        make_fragrance(session, brand=brand, name=name)
    service = SurfaceChoiceService(session)
    initial = service.choose(
        user.id, "discovery", SurfaceChoiceRequest(idempotency_key=uuid4(), advance=False)
    )
    following = service.choose(
        user.id,
        "discovery",
        SurfaceChoiceRequest(
            batch_id=initial.batch_id,
            idempotency_key=uuid4(),
            expected_candidate_id=initial.candidate_id,
        ),
    )
    assert initial.candidate_id != following.candidate_id
    assert str(original.fragrance.id) not in {initial.candidate_id, following.candidate_id}
    assert following.options_exhausted
