"""Operator-only inference diagnostics; never exposes member context or credentials.

Run `python -m scentiq_api.inference_status` inside the API runtime. The optional
--smoke flag dispatches one synthetic request charged to the shared allowance.
"""

import argparse
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from scentiq_api.config import Settings
from scentiq_api.database import create_database_engine
from scentiq_api.models.ai_usage import AIUsageMonth


def inference_status(session: Session, settings: Settings) -> dict[str, Any]:
    month = datetime.now(UTC).strftime("%Y-%m")
    ledger = session.get(AIUsageMonth, month)
    charged = ledger.charged_microusd / 1_000_000 if ledger else 0.0
    return {
        "month_utc": month,
        "provider_configured": bool(
            settings.azure_openai_endpoint and settings.azure_openai_deployment
        ),
        "deployment": settings.azure_openai_deployment,
        "charged_usd": charged,
        "remaining_usd": max(0, settings.ai_monthly_budget_usd - charged),
        "monthly_budget_usd": settings.ai_monthly_budget_usd,
        "shadow_enabled": settings.ai_ranking_shadow_enabled,
        "surfaces": {
            surface: getattr(settings, f"ai_ranking_{surface}_enabled")
            for surface in ("today", "week", "discovery", "layering", "advisor")
        },
    }


def smoke_check(session: Session, settings: Settings) -> bool:
    from scentiq_api.services.ai_ranking import (
        _request_ranking,
        request_cost,
        reserve_budget,
        settle_budget,
    )

    if not settings.azure_openai_endpoint or not settings.azure_openai_deployment:
        return False
    reservation = reserve_budget(
        session.get_bind(), settings, request_cost(settings, 4096, settings.ai_max_output_tokens)
    )
    if reservation is None:
        return False
    response = _request_ranking(
        settings,
        {
            "model": settings.azure_openai_deployment,
            "store": False,
            "max_output_tokens": settings.ai_max_output_tokens,
            "input": "Return the JSON object with ok equal to true.",
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "smoke_check",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {"ok": {"type": "boolean"}},
                        "required": ["ok"],
                        "additionalProperties": False,
                    },
                }
            },
        },
    )
    usage = response.get("usage", {})
    input_tokens, output_tokens = usage.get("input_tokens"), usage.get("output_tokens")
    if (
        type(input_tokens) is int
        and type(output_tokens) is int
        and input_tokens >= 0
        and output_tokens >= 0
    ):
        settle_budget(
            session.get_bind(), reservation, request_cost(settings, input_tokens, output_tokens)
        )
    text = "".join(
        part.get("text", "")
        for item in response.get("output", [])
        for part in item.get("content", [])
        if part.get("type") == "output_text"
    )
    return response.get("status") == "completed" and json.loads(text) == {"ok": True}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--smoke", action="store_true", help="Dispatch one budgeted synthetic inference"
    )
    args = parser.parse_args()
    settings = Settings()
    engine = create_database_engine(settings.database_url_value)
    try:
        with Session(engine) as session:
            output = inference_status(session, settings)
            if args.smoke:
                try:
                    passed = smoke_check(session, settings)
                except Exception:
                    # Never print provider response bodies or credential errors.
                    passed = False
                output["smoke_passed"] = passed
                print(json.dumps(output, sort_keys=True))
                if not passed:
                    raise SystemExit(1)
            else:
                print(json.dumps(output, sort_keys=True))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
