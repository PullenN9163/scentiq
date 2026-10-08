from __future__ import annotations

from decimal import Decimal

import pytest

from scentiq_api.catalog_import.normalize import (
    decode_luckyscent,
    fold,
    longevity_score,
    name_key,
    parse_concentration,
    parse_decimal,
    parse_python_list,
    positional_weights,
    projection_level,
    repair_mojibake,
    season_weights,
    valid_year,
)


def test_fold_is_accent_insensitive_and_normalizes_ampersands() -> None:
    assert fold("  Été & Bois—No. 2  ") == "ete and bois no 2"


def test_mojibake_repair_only_changes_clean_round_trips() -> None:
    assert repair_mojibake("Tabac Ã‰carlate") == "Tabac Écarlate"
    assert repair_mojibake("Tabac Écarlate") == "Tabac Écarlate"


def test_luckyscent_decode_falls_back_for_undefined_cp1252_bytes() -> None:
    assert decode_luckyscent(b"Name\nA\x9dB\n") == "Name\nA\x9dB\n"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("1,42", Decimal("1.42")), ("3.75", Decimal("3.75")), ("NA", None), ("", None)],
)
def test_decimal_parser_handles_comma_and_missing_values(
    raw: str, expected: Decimal | None
) -> None:
    assert parse_decimal(raw) == expected


def test_python_list_parser_is_literal_only_and_tolerates_bad_input() -> None:
    assert parse_python_list("['woody', 'amber']") == ("woody", "amber")
    assert parse_python_list("__import__('os').system('bad')") == ()
    assert parse_python_list("{'not': 'a list'}") == ()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Samsara Eau de Parfum", "Eau de Parfum"),
        ("Scent EDP", "Eau de Parfum"),
        ("Oil Perfume Oil", "Perfume Oil"),
        ("Solid Scent Solid Perfume", "Solid Perfume"),
        ("Plain Scent", None),
    ],
)
def test_concentration_parser_returns_canonical_labels(raw: str, expected: str | None) -> None:
    assert parse_concentration(raw) == expected


def test_name_key_removes_brand_concentration_year_and_gender_suffixes() -> None:
    assert name_key("Samsara Guerlain 1989 Eau de Parfum", "Guerlain") == "samsara"
    assert name_key("9am Afnanfor women", "Afnan") == "9am"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(1699, None), ("1700", 1700), (2027.0, 2027), ("2100", 2100), (2101, None), (True, None)],
)
def test_year_is_clamped(raw: object, expected: int | None) -> None:
    assert valid_year(raw) == expected


def test_community_metric_mappings_require_enough_votes() -> None:
    assert longevity_score(Decimal("1"), 5) == Decimal("0.0")
    assert longevity_score(Decimal("3"), 5) == Decimal("5.0")
    assert longevity_score(Decimal("5"), 5) == Decimal("10.0")
    assert longevity_score(Decimal("5"), 4) is None
    assert projection_level(Decimal("1.49"), 5) == "intimate"
    assert projection_level(Decimal("1.50"), 5) == "moderate"
    assert projection_level(Decimal("2.49"), 5) == "moderate"
    assert projection_level(Decimal("2.50"), 5) == "strong"
    assert projection_level(Decimal("3"), 4) is None


def test_season_and_positional_weights_follow_the_import_contract() -> None:
    assert season_weights({"winter": 2, "spring": 4, "summer": 8, "autumn": 6}) == {
        "winter": Decimal("0.25"),
        "spring": Decimal("0.50"),
        "summer": Decimal("1.00"),
        "fall": Decimal("0.75"),
    }
    assert season_weights({"winter": 1, "summer": 3}) == {}
    assert positional_weights(("woody", "amber", "floral", "fresh", "green", "extra")) == (
        ("woody", Decimal("1.0")),
        ("amber", Decimal("0.8")),
        ("floral", Decimal("0.6")),
        ("fresh", Decimal("0.4")),
        ("green", Decimal("0.2")),
    )
