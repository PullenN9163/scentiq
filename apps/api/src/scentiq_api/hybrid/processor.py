from __future__ import annotations

from typing import Any

from scentiq_api.hybrid.contracts import RecommendationJobInput


def process_recommendation(_: RecommendationJobInput) -> dict[str, Any]:
    """Return the stable bundle envelope populated by the scoring task."""
    return {
        "discovery": [],
        "layering": {"safe": [], "contrast": [], "experimental": []},
    }
