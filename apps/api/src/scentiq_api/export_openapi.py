"""Write the OpenAPI document that the web app's typed contracts are generated from.

    uv run --directory apps/api python -m scentiq_api.export_openapi > openapi.json

The document must not depend on deployment configuration, so this uses fixed
placeholder settings and never opens a database connection.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

# Fixed, non-secret placeholders: the schema must be byte-identical on every
# machine, so nothing here may come from the ambient environment.
_EXPORT_SETTINGS = {
    "SCENTIQ_ENV": "test",
    "DATABASE_URL": "postgresql+psycopg://contract:contract@localhost/contract",
    "CORS_ORIGINS": "http://localhost:3000",
    "CLERK_ISSUER": "https://contract.example.invalid",
    "CLERK_AUDIENCE": "scentiq-web",
}


def build_document() -> dict[str, Any]:
    # `scentiq_api.main` builds an application at import time, so the settings
    # have to be in the environment before it is imported.
    for name, value in _EXPORT_SETTINGS.items():
        os.environ[name] = value

    from scentiq_api.config import Settings
    from scentiq_api.main import create_app

    settings = Settings()
    # A no-op probe keeps the export free of any database connection.
    application = create_app(settings, database_probe=lambda: None)
    document: dict[str, Any] = application.openapi()
    return document


def main() -> int:
    # sort_keys makes the output byte-stable, so drift detection is meaningful.
    json.dump(build_document(), sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
