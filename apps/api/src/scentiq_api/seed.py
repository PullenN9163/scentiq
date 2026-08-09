import json
from collections.abc import Sequence
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from scentiq_api.config import DEFAULT_DEMO_USER_ID, Settings
from scentiq_api.database import create_database_engine
from scentiq_api.models import (
    Accord,
    Brand,
    Fragrance,
    FragranceAccord,
    FragranceNote,
    FragranceOccasion,
    FragranceSeason,
    Note,
    User,
    UserCollectionItem,
    UserPreference,
)

DEMO_USER_ID = DEFAULT_DEMO_USER_ID

BRANDS = [
    {
        "id": UUID("01000000-0000-4000-8000-000000000001"),
        "name": "ScentIQ Atelier",
        "slug": "scentiq-atelier",
    },
    {
        "id": UUID("01000000-0000-4000-8000-000000000002"),
        "name": "ScentIQ Botanica",
        "slug": "scentiq-botanica",
    },
    {
        "id": UUID("01000000-0000-4000-8000-000000000003"),
        "name": "ScentIQ Studio",
        "slug": "scentiq-studio",
    },
]

NOTES = [
    ("Bergamot", "bergamot"),
    ("Cedar", "cedar"),
    ("Iris", "iris"),
    ("Fig", "fig"),
    ("Neroli", "neroli"),
    ("Labdanum", "labdanum"),
    ("Vanilla", "vanilla"),
    ("Moss", "moss"),
    ("Lavender", "lavender"),
    ("Saffron", "saffron"),
    ("Violet", "violet"),
    ("Sea Salt", "sea-salt"),
    ("Amberwood", "amberwood"),
    ("Cardamom", "cardamom"),
    ("Patchouli", "patchouli"),
    ("Tonka Bean", "tonka-bean"),
    ("Vetiver", "vetiver"),
    ("Mandarin", "mandarin"),
]

ACCORDS = [
    ("Amber", "amber"),
    ("Woody", "woody"),
    ("Citrus", "citrus"),
    ("Floral", "floral"),
    ("Fresh", "fresh"),
    ("Aromatic", "aromatic"),
    ("Green", "green"),
    ("Spicy", "spicy"),
    ("Marine", "marine"),
    ("Powdery", "powdery"),
]

FRAGRANCE_NAMES = [
    "Amber Atlas",
    "Cedar Veil",
    "Midnight Resin",
    "Silk Ember",
    "Winter Library",
    "Citrus Canopy",
    "Fig Garden",
    "Lavender Current",
    "Moss After Rain",
    "Neroli Drift",
    "Coastal Static",
    "Iris Paper",
    "Mineral Skin",
    "Saffron Signal",
    "Violet Circuit",
]


def _uuid(namespace: int, sequence: int) -> UUID:
    return UUID(f"{namespace:02d}000000-0000-4000-8000-{sequence:012d}")


def _upsert(
    session: Session,
    model: type[Any],
    rows: Sequence[dict[str, Any]],
    update_columns: Sequence[str],
) -> None:
    statement = insert(model).values(list(rows))
    session.execute(
        statement.on_conflict_do_update(
            index_elements=["id"],
            set_={column: getattr(statement.excluded, column) for column in update_columns},
        )
    )


def _fragrance_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, name in enumerate(FRAGRANCE_NAMES, start=1):
        rows.append(
            {
                "id": _uuid(10, index),
                "brand_id": BRANDS[(index - 1) // 5]["id"],
                "name": name,
                "concentration": "eau_de_parfum",
                "release_year": 2026,
                "description": (
                    "A warm amber study from the fictional ScentIQ demo catalog."
                    if index == 1
                    else f"A fictional fragrance created for the ScentIQ demo catalog: {name}."
                ),
                "image_blob_path": None,
                "longevity_score": Decimal("8.2") if index == 1 else Decimal("7.0"),
                "projection_level": "moderate",
            }
        )
    return rows


def _association_rows() -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    note_rows: list[dict[str, Any]] = []
    accord_rows: list[dict[str, Any]] = []
    season_rows: list[dict[str, Any]] = []
    occasion_rows: list[dict[str, Any]] = []
    stages = ("top", "middle", "base")
    seasons = ("spring", "summer", "fall", "winter")
    occasions = ("work", "casual", "date", "dinner", "party")

    for index in range(1, 16):
        fragrance_id = _uuid(10, index)
        if index == 1:
            note_rows.extend(
                [
                    {"fragrance_id": fragrance_id, "note_id": _uuid(2, 1), "stage": "top"},
                    {
                        "fragrance_id": fragrance_id,
                        "note_id": _uuid(2, 6),
                        "stage": "middle",
                    },
                    {"fragrance_id": fragrance_id, "note_id": _uuid(2, 7), "stage": "base"},
                ]
            )
            accord_rows.extend(
                [
                    {
                        "fragrance_id": fragrance_id,
                        "accord_id": _uuid(3, 1),
                        "weight": Decimal("0.90"),
                    },
                    {
                        "fragrance_id": fragrance_id,
                        "accord_id": _uuid(3, 8),
                        "weight": Decimal("0.55"),
                    },
                ]
            )
            season_rows.extend(
                [
                    {
                        "fragrance_id": fragrance_id,
                        "season": "fall",
                        "weight": Decimal("0.90"),
                    },
                    {
                        "fragrance_id": fragrance_id,
                        "season": "winter",
                        "weight": Decimal("1.00"),
                    },
                ]
            )
            occasion_rows.extend(
                [
                    {
                        "fragrance_id": fragrance_id,
                        "occasion": "date",
                        "weight": Decimal("0.80"),
                    },
                    {
                        "fragrance_id": fragrance_id,
                        "occasion": "dinner",
                        "weight": Decimal("0.90"),
                    },
                ]
            )
            continue

        for offset, stage in enumerate(stages):
            note_rows.append(
                {
                    "fragrance_id": fragrance_id,
                    "note_id": _uuid(2, ((index + offset - 1) % len(NOTES)) + 1),
                    "stage": stage,
                }
            )
        accord_rows.append(
            {
                "fragrance_id": fragrance_id,
                "accord_id": _uuid(3, ((index - 1) % len(ACCORDS)) + 1),
                "weight": Decimal("0.75"),
            }
        )
        season_rows.append(
            {
                "fragrance_id": fragrance_id,
                "season": seasons[(index - 1) % len(seasons)],
                "weight": Decimal("0.80"),
            }
        )
        occasion_rows.append(
            {
                "fragrance_id": fragrance_id,
                "occasion": occasions[(index - 1) % len(occasions)],
                "weight": Decimal("0.80"),
            }
        )
    return note_rows, accord_rows, season_rows, occasion_rows


def _upsert_associations(session: Session) -> None:
    note_rows, accord_rows, season_rows, occasion_rows = _association_rows()
    for model, rows, conflict_columns, update_columns in (
        (FragranceNote, note_rows, ["fragrance_id", "note_id", "stage"], []),
        (FragranceAccord, accord_rows, ["fragrance_id", "accord_id"], ["weight"]),
        (FragranceSeason, season_rows, ["fragrance_id", "season"], ["weight"]),
        (FragranceOccasion, occasion_rows, ["fragrance_id", "occasion"], ["weight"]),
    ):
        statement = insert(model).values(rows)
        if update_columns:
            statement = statement.on_conflict_do_update(
                index_elements=conflict_columns,
                set_={column: getattr(statement.excluded, column) for column in update_columns},
            )
        else:
            statement = statement.on_conflict_do_nothing(index_elements=conflict_columns)
        session.execute(statement)


def _collection_rows() -> list[dict[str, Any]]:
    ownership_types = (
        "bottle",
        "decant",
        "sample",
        "bottle",
        "sample",
        "decant",
        "bottle",
        "sample",
    )
    rows: list[dict[str, Any]] = []
    for index, ownership_type in enumerate(ownership_types, start=1):
        size = {
            "bottle": Decimal("100.00"),
            "decant": Decimal("10.00"),
            "sample": Decimal("2.00"),
        }[ownership_type]
        rows.append(
            {
                "id": _uuid(40, index),
                "user_id": DEMO_USER_ID,
                "fragrance_id": _uuid(10, index),
                "ownership_type": ownership_type,
                "bottle_size_ml": size,
                "remaining_ml": size,
                "purchase_price": Decimal("145.00") if ownership_type == "bottle" else None,
                "purchase_date": None,
                "user_rating": 4 if index == 1 else None,
                "custom_longevity": None,
                "custom_projection": None,
                "status": "owned",
            }
        )
    return rows


def seed(session: Session) -> dict[str, int]:
    _upsert(
        session,
        User,
        [
            {
                "id": DEMO_USER_ID,
                "email": "demo@scentiq.example",
                "display_name": "ScentIQ Demo",
                "is_demo": True,
            }
        ],
        ["email", "display_name", "is_demo"],
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
    _upsert(session, Brand, BRANDS, ["name", "slug"])
    _upsert(
        session,
        Note,
        [
            {"id": _uuid(2, index), "name": name, "slug": slug}
            for index, (name, slug) in enumerate(NOTES, start=1)
        ],
        ["name", "slug"],
    )
    _upsert(
        session,
        Accord,
        [
            {"id": _uuid(3, index), "name": name, "slug": slug}
            for index, (name, slug) in enumerate(ACCORDS, start=1)
        ],
        ["name", "slug"],
    )
    _upsert(
        session,
        Fragrance,
        _fragrance_rows(),
        [
            "brand_id",
            "name",
            "concentration",
            "release_year",
            "description",
            "image_blob_path",
            "longevity_score",
            "projection_level",
        ],
    )
    _upsert_associations(session)
    _upsert(
        session,
        UserCollectionItem,
        _collection_rows(),
        [
            "user_id",
            "fragrance_id",
            "ownership_type",
            "bottle_size_ml",
            "remaining_ml",
            "purchase_price",
            "purchase_date",
            "user_rating",
            "custom_longevity",
            "custom_projection",
            "status",
        ],
    )

    return {
        "accords": session.scalar(select(func.count()).select_from(Accord)) or 0,
        "brands": session.scalar(select(func.count()).select_from(Brand)) or 0,
        "collection_items": session.scalar(select(func.count()).select_from(UserCollectionItem))
        or 0,
        "fragrances": session.scalar(select(func.count()).select_from(Fragrance)) or 0,
        "notes": session.scalar(select(func.count()).select_from(Note)) or 0,
        "users": session.scalar(select(func.count()).select_from(User)) or 0,
    }


def main() -> None:
    engine = create_database_engine(Settings().database_url_value)
    try:
        with Session(engine) as session, session.begin():
            counts = seed(session)
        print(json.dumps(counts, sort_keys=True))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
