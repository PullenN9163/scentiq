from __future__ import annotations

import ast
import re
import unicodedata
from collections.abc import Mapping, Sequence
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

_MISSING = {"", "na", "n/a", "none", "null", "unknown"}
_NON_ALPHANUMERIC = re.compile(r"[^a-z0-9]+")
_YEAR_TOKEN = re.compile(r"(?<!\d)(?:17|18|19|20)\d{2}(?!\d)")
_GENDER_SUFFIX = re.compile(r"\bfor\s+(?:women\s+and\s+men|men\s+and\s+women|women|men)\b")
_CONCENTRATIONS: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(rf"\b{pattern}\b", re.IGNORECASE), label)
    for pattern, label in (
        (r"extrait\s+de\s+parfum", "Extrait de Parfum"),
        (r"eau\s+de\s+parfum", "Eau de Parfum"),
        (r"eau\s+de\s+toilette", "Eau de Toilette"),
        (r"eau\s+de\s+cologne", "Eau de Cologne"),
        (r"perfume\s+oil", "Perfume Oil"),
        (r"solid\s+perfume", "Solid Perfume"),
        (r"after\s+shave", "After Shave"),
        (r"body\s+spray", "Body Spray"),
        (r"parfum", "Parfum"),
        (r"extrait", "Extrait"),
        (r"cologne", "Cologne"),
        (r"edp", "Eau de Parfum"),
        (r"edt", "Eau de Toilette"),
        (r"edc", "Eau de Cologne"),
    )
)


def meaningful_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text if text.casefold() not in _MISSING else None


def fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.replace("&", " and "))
    without_marks = "".join(char for char in normalized if not unicodedata.combining(char))
    return _NON_ALPHANUMERIC.sub(" ", without_marks.casefold()).strip()


def brand_key(value: str) -> str:
    return fold(value)


def repair_mojibake(value: str) -> str:
    try:
        repaired = value.encode("cp1252").decode("utf-8")
    except UnicodeEncodeError, UnicodeDecodeError:
        return value
    return repaired


def decode_luckyscent(payload: bytes) -> str:
    try:
        return payload.decode("cp1252")
    except UnicodeDecodeError:
        return payload.decode("latin-1")


def parse_decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    text = meaningful_text(value) if isinstance(value, str) else str(value)
    if text is None:
        return None
    try:
        return Decimal(text.replace(",", "."))
    except InvalidOperation:
        return None


def parse_int(value: object) -> int | None:
    number = parse_decimal(value)
    if number is None or number != number.to_integral_value():
        return None
    return int(number)


def parse_python_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, str):
        return ()
    try:
        parsed = ast.literal_eval(value)
    except SyntaxError, ValueError:
        return ()
    if not isinstance(parsed, list):
        return ()
    return tuple(text for item in parsed if (text := meaningful_text(item)) is not None)


def parse_concentration(value: object) -> str | None:
    text = meaningful_text(value)
    if text is None:
        return None
    for pattern, label in _CONCENTRATIONS:
        if pattern.search(text):
            return label
    return None


def valid_year(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value).strip())
    except InvalidOperation:
        return None
    if number != number.to_integral_value():
        return None
    year = int(number)
    return year if 1700 <= year <= 2100 else None


def year_hint(value: str) -> int | None:
    match = _YEAR_TOKEN.search(value)
    return valid_year(match.group()) if match else None


def name_key(name: str, brand: str | None = None) -> str:
    key = fold(name)
    for pattern, _label in _CONCENTRATIONS:
        key = pattern.sub(" ", key)
    key = _YEAR_TOKEN.sub(" ", key)
    key = _GENDER_SUFFIX.sub(" ", key)
    if brand and (brand_folded := fold(brand)):
        brand_pattern = re.compile(rf"(?<![a-z0-9]){re.escape(brand_folded)}(?=for\b|[^a-z0-9]|$)")
        key = brand_pattern.sub(" ", key)
        key = _GENDER_SUFFIX.sub(" ", key)
    return _NON_ALPHANUMERIC.sub(" ", key).strip()


def normalize_gender(value: object) -> str | None:
    text = fold(str(value or ""))
    if text in {"female", "for women", "women"}:
        return "female"
    if text in {"male", "for men", "men"}:
        return "male"
    if text in {
        "unisex",
        "for women and men",
        "for men and women",
        "women and men",
        "men and women",
    }:
        return "unisex"
    return None


def longevity_score(average: Decimal | None, votes: int) -> Decimal | None:
    if average is None or votes < 5 or not Decimal("1") <= average <= Decimal("5"):
        return None
    return ((average - Decimal("1")) * Decimal("2.5")).quantize(
        Decimal("0.1"), rounding=ROUND_HALF_UP
    )


def projection_level(average: Decimal | None, votes: int) -> str | None:
    if average is None or votes < 5:
        return None
    if average < Decimal("1.5"):
        return "intimate"
    if average < Decimal("2.5"):
        return "moderate"
    return "strong"


def season_weights(votes: Mapping[str, object]) -> dict[str, Decimal]:
    normalized = {
        ("fall" if key == "autumn" else key): parsed
        for key, value in votes.items()
        if key in {"winter", "spring", "summer", "autumn", "fall"}
        and (parsed := parse_int(value)) is not None
        and parsed >= 0
    }
    if sum(normalized.values()) < 5 or not normalized:
        return {}
    maximum = max(normalized.values())
    if maximum <= 0:
        return {}
    return {
        key: (Decimal(value) / Decimal(maximum)).quantize(Decimal("0.01"))
        for key, value in normalized.items()
    }


def positional_weights(values: Sequence[str]) -> tuple[tuple[str, Decimal], ...]:
    weights = tuple(Decimal(value) for value in ("1.0", "0.8", "0.6", "0.4", "0.2"))
    return tuple((name, weight) for name, weight in zip(values, weights, strict=False))
