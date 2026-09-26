from __future__ import annotations

import os
from decimal import Decimal
from uuid import UUID

from sqlalchemy import create_engine

from scentiq_api.catalog_import.load import load_catalog
from scentiq_api.catalog_import.merge import build_canonical_catalog
from scentiq_api.catalog_import.types import AccordValue, NoteValue, SourceRecord
from scentiq_api.seed import DEMO_FRAGRANTICA_IDS


def load_test_catalog() -> None:
    """Load an explicitly fictional catalog for integration tests only."""
    names = (
        "Amber Atlas",
        "Bergamot Bay",
        "Cedar Current",
        "Desert Bloom",
        "Ember Archive",
        "Fig Horizon",
        "Garden Static",
        "Hinoki Signal",
        "Iris Circuit",
        "Juniper Loom",
        "Kelp Meridian",
        "Leather Comet",
        "Moss Relay",
        "Neroli Frame",
        "Orris Terminal",
    )
    source_ids = (*DEMO_FRAGRANTICA_IDS, "test-13", "test-14", "test-15")
    records = [
        SourceRecord(
            source="fragrantica",
            source_record_id=source_id,
            source_url=f"https://example.test/fragrance/{source_id}",
            name=name,
            brand="ScentIQ Test Atelier",
            brand_key="scentiq test atelier",
            name_key=name.casefold(),
            concentration="eau_de_parfum",
            release_year=2026,
            description=(
                "A warm amber study from the fictional ScentIQ test catalog."
                if index == 0
                else f"Fictional integration fixture {index + 1}."
            ),
            longevity_score=Decimal("8.2"),
            projection_level="moderate",
            notes=(
                NoteValue("Bergamot", "bergamot", "top"),
                NoteValue("Labdanum", "labdanum", "middle"),
                NoteValue("Vanilla", "vanilla", "base"),
            )
            if index == 0
            else (),
            accords=(AccordValue("Amber", "amber", Decimal("0.9")),)
            if index == 0
            else (),
            seasons={"fall": Decimal("0.9"), "winter": Decimal("1.0")}
            if index == 0
            else {},
        )
        for index, (source_id, name) in enumerate(zip(source_ids, names, strict=True))
    ]
    existing_sources = {
        ("fragrantica", source_id): UUID(f"10000000-0000-4000-8000-{index:012d}")
        for index, source_id in enumerate(source_ids, start=1)
    }
    catalog = build_canonical_catalog(records, {}, existing_sources)
    engine = create_engine(os.environ["DATABASE_URL"])
    try:
        connection = engine.raw_connection()
        try:
            load_catalog(connection.driver_connection, catalog, inputs={"fixture": {}})
        finally:
            connection.close()
    finally:
        engine.dispose()
