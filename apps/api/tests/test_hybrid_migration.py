from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_intelligence_migration_extends_the_hybrid_schema_head() -> None:
    api_root = Path(__file__).parents[1]
    config = Config(str(api_root / "alembic.ini"))
    config.set_main_option("script_location", str(api_root / "migrations"))

    scripts = ScriptDirectory.from_config(config)

    assert scripts.get_heads() == ["20261007_0008_layer_stacks"]
    assert scripts.get_revision("20261005_0007").down_revision == "20260928_0006"
