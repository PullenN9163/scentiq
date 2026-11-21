"""Filter-driven spray allocation and body-zone placement for a blend.

Placement guidance follows published layering advice: spray the heavier, longer-lasting
scent first on warm, broad areas; put lighter scents on different pulse points so they
layer rather than stack; do not rub; keep to two or three scents. Starting points only.
"""

from __future__ import annotations

from typing import get_args

from scentiq_api.schemas.layering import SprayZone, SprayZoneApplication

ZONES: tuple[str, ...] = get_args(SprayZone)
# Zones ordered by suitability for a heavy/base-led scent, then lighter ones.
BASE_ZONES: tuple[SprayZone, ...] = ("chest", "back_of_neck", "inner_elbows")
LIGHT_ZONES: tuple[SprayZone, ...] = ("neck", "wrists", "behind_ears", "behind_knees")


def allocate_sprays(
    count: int,
    total: int,
    *,
    anchor_index: int,
    favored_index: int | None,
    bridge_index: int | None,
) -> list[int]:
    """Spread ``total`` sprays over ``count`` scents, one each minimum.

    Extras go to the scent a filter favours (e.g. the warmest for 'warmer'); without one,
    alternately to the anchor then the bridge, preserving the previous behaviour.
    """
    sprays = [1] * count
    for extra in range(total - count):
        if favored_index is not None and extra < 2:
            sprays[favored_index] += 1
        elif extra % 2 == 0:
            sprays[anchor_index] += 1
        else:
            sprays[bridge_index if bridge_index is not None else anchor_index] += 1
    return [min(6, value) for value in sprays]


def assign_zones(sprays: list[int], heaviness: list[float]) -> list[list[SprayZoneApplication]]:
    """Give each scent its own zones. The heaviest takes the broad base zones first."""
    order = sorted(range(len(sprays)), key=lambda index: (-heaviness[index], index))
    result: list[list[SprayZoneApplication]] = [[] for _ in sprays]
    base_pool = list(BASE_ZONES)
    light_pool = list(LIGHT_ZONES)
    for rank, index in enumerate(order):
        pool = base_pool if rank == 0 else light_pool
        remaining = sprays[index]
        # Prefer one spray per zone; stack two only when out of distinct zones.
        zones: list[SprayZone] = []
        while remaining > 0:
            if pool:
                zones.append(pool.pop(0))
            elif light_pool:
                zones.append(light_pool.pop(0))
            elif base_pool:
                zones.append(base_pool.pop(0))
            else:
                zones.append(zones[-1] if zones else "chest")
            remaining -= 1
        counts: dict[SprayZone, int] = {}
        for zone in zones:
            counts[zone] = counts.get(zone, 0) + 1
        result[index] = [
            SprayZoneApplication(zone=zone, sprays=min(3, count)) for zone, count in counts.items()
        ]
    return result


def total_for(
    *,
    mode: str,
    goal: str | None,
    strong_count: int,
    coverage: float,
    maximum: int | None,
    count: int,
) -> tuple[int, list[str]]:
    """Total sprays and the filter effects that shaped it."""
    effects: list[str] = []
    total = 3 if strong_count >= 2 else 4 if strong_count else 6
    if goal in ("softer", "more_intimate"):
        total = min(total, 3)
        effects.append("Softer goal: capped at 3 sprays.")
    elif goal == "more_projection" and strong_count < 2:
        total = min(6, total + 1)
        effects.append("Boost projection: one extra spray.")
    if goal in ("fresher", "cleaner", "daytime"):
        total = min(total, 4)
        effects.append("Light goal: kept to 4 sprays or fewer.")
    if mode == "safe":
        total = min(total, 4)
        effects.append("Safe mode: kept to 4 sprays or fewer.")
    if coverage < 0.65:
        total = min(total, 4)
    return max(count, min(total, maximum or 6)), effects
