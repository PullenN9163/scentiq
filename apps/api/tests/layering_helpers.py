from decimal import Decimal

from domain_fixtures import make_brand, make_collection_item, make_fragrance, make_user
from sqlalchemy.orm import Session

from scentiq_api.models import Accord, Fragrance, FragranceAccord, User


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
