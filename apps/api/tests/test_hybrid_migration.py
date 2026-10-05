from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_hybrid_migration_is_the_single_schema_head() -> None:
    api_root = Path(__file__).parents[1]
    config = Config(str(api_root / "alembic.ini"))
    config.set_main_option("script_location", str(api_root / "migrations"))

    scripts = ScriptDirectory.from_config(config)

    assert scripts.get_heads() == ["20261005_0005"]
    assert scripts.get_revision("20261005_0005").down_revision == "20260925_0004"
