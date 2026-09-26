import json
from decimal import Decimal
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from scentiq_api.config import DEFAULT_DEMO_USER_ID, Settings
from scentiq_api.database import create_database_engine
from scentiq_api.models import Fragrance, FragranceSource, User, UserCollectionItem, UserPreference

DEMO_USER_ID = DEFAULT_DEMO_USER_ID

# Reviewed high-popularity Fragrantica records across distinct olfactory families.
DEMO_FRAGRANTICA_IDS = (
    "1825",  # Tobacco Vanille — Oriental Spicy
    "33519",  # Baccarat Rouge 540 — Oriental Floral
    "62615",  # Angels' Share — Oriental Vanilla
    "34696",  # Club de Nuit Intense Man — Woody Spicy
    "9828",  # Aventus — Chypre Fruity
    "31623",  # By the Fireplace — Woody
    "50757",  # Y Eau de Parfum — Aromatic Fougere
    "485",  # Light Blue — Floral Fruity
    "30529",  # XJ 1861 Naxos — Citrus Gourmand
    "25967",  # Bleu de Chanel Eau de Parfum — Woody Aromatic
    "20541",  # Jazz Club — Leather
    "410",  # Acqua di Gio — Aromatic Aquatic
)


def _uuid(sequence: int) -> UUID:
    return UUID(f"40000000-0000-4000-8000-{sequence:012d}")


def _catalog_fragrance_ids(session: Session) -> list[UUID]:
    rows = session.execute(
        select(FragranceSource.source_record_id, FragranceSource.fragrance_id)
        .join(Fragrance, Fragrance.id == FragranceSource.fragrance_id)
        .where(
            FragranceSource.source == "fragrantica",
            FragranceSource.source_record_id.in_(DEMO_FRAGRANTICA_IDS),
            Fragrance.owner_user_id.is_(None),
        )
    ).all()
    by_source_id = {source_id: fragrance_id for source_id, fragrance_id in rows}
    missing = [source_id for source_id in DEMO_FRAGRANTICA_IDS if source_id not in by_source_id]
    if missing:
        raise RuntimeError(
            "The shared catalog has not been imported. Run the catalog importer before seed; "
            "missing Fragrantica ids: " + ", ".join(missing)
        )
    return [by_source_id[source_id] for source_id in DEMO_FRAGRANTICA_IDS]


def seed(session: Session) -> dict[str, int]:
    fragrance_ids = _catalog_fragrance_ids(session)
    user_statement = insert(User).values(
        id=DEMO_USER_ID,
        email="demo@scentiq.example",
        display_name="ScentIQ Demo",
        is_demo=True,
    )
    session.execute(
        user_statement.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "email": user_statement.excluded.email,
                "display_name": user_statement.excluded.display_name,
                "is_demo": user_statement.excluded.is_demo,
            },
        )
    )
    preference_statement = insert(UserPreference).values(
        user_id=DEMO_USER_ID,
        preferred_season="fall",
        preferred_occasion="casual",
        preferred_projection="moderate",
        preferred_longevity=Decimal("7.0"),
        maximum_sprays=6,
    )
    session.execute(
        preference_statement.on_conflict_do_update(
            index_elements=["user_id"],
            set_={
                "preferred_season": preference_statement.excluded.preferred_season,
                "preferred_occasion": preference_statement.excluded.preferred_occasion,
                "preferred_projection": preference_statement.excluded.preferred_projection,
                "preferred_longevity": preference_statement.excluded.preferred_longevity,
                "maximum_sprays": preference_statement.excluded.maximum_sprays,
            },
        )
    )

    collection_ids = [_uuid(index) for index in range(1, len(fragrance_ids) + 1)]
    collection_statement = insert(UserCollectionItem).values(
        [
            {
                "id": collection_id,
                "user_id": DEMO_USER_ID,
                "fragrance_id": fragrance_id,
                "ownership_type": "sample",
                "bottle_size_ml": None,
                "remaining_ml": None,
                "purchase_price": None,
                "purchase_date": None,
                "user_rating": None,
                "custom_longevity": None,
                "custom_projection": None,
                "status": "owned",
            }
            for collection_id, fragrance_id in zip(collection_ids, fragrance_ids, strict=True)
        ]
    )
    session.execute(
        collection_statement.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "user_id": collection_statement.excluded.user_id,
                "fragrance_id": collection_statement.excluded.fragrance_id,
                "ownership_type": collection_statement.excluded.ownership_type,
                "bottle_size_ml": collection_statement.excluded.bottle_size_ml,
                "remaining_ml": collection_statement.excluded.remaining_ml,
                "purchase_price": collection_statement.excluded.purchase_price,
                "purchase_date": collection_statement.excluded.purchase_date,
                "user_rating": collection_statement.excluded.user_rating,
                "custom_longevity": collection_statement.excluded.custom_longevity,
                "custom_projection": collection_statement.excluded.custom_projection,
                "status": collection_statement.excluded.status,
            },
        )
    )
    session.execute(
        delete(UserCollectionItem).where(
            UserCollectionItem.user_id == DEMO_USER_ID,
            UserCollectionItem.id.not_in(collection_ids),
        )
    )

    return {
        "collection_items": session.scalar(
            select(func.count())
            .select_from(UserCollectionItem)
            .where(UserCollectionItem.user_id == DEMO_USER_ID)
        )
        or 0,
        "fragrances": session.scalar(
            select(func.count()).select_from(Fragrance).where(Fragrance.owner_user_id.is_(None))
        )
        or 0,
        "users": session.scalar(select(func.count()).select_from(User)) or 0,
    }


def main() -> None:
    engine = create_database_engine(Settings().database_url_value)
    try:
        with Session(engine) as session, session.begin():
            counts = seed(session)
        print(json.dumps(counts, sort_keys=True))
    except RuntimeError as error:
        raise SystemExit(str(error)) from error
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
