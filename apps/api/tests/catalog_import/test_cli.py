from pathlib import Path

import pytest

from scentiq_api.catalog_import.__main__ import (
    _input_manifest,
    _selected_sources,
    _streams,
    main,
)


def test_only_accepts_comma_separated_and_repeated_source_groups() -> None:
    assert _selected_sources(["fragrantica,parfumo", "luckyscent"]) == {
        "fragrantica",
        "parfumo",
        "luckyscent",
    }


def test_only_rejects_unknown_source() -> None:
    with pytest.raises(ValueError, match="unknown catalog source"):
        _selected_sources(["fragrantica,unknown"])


def test_partial_import_is_dry_run_only() -> None:
    with pytest.raises(SystemExit, match="2"):
        main(["--only", "parfumo"])


def test_selected_streams_require_only_their_physical_inputs(tmp_path: Path) -> None:
    (tmp_path / "parfumo_data_clean.csv").write_text("", encoding="utf-8")

    assert len(_streams(tmp_path, {"parfumo"})) == 1


def test_manifest_contains_only_selected_inputs_and_no_operator_path(tmp_path: Path) -> None:
    source = tmp_path / "parfumo_data_clean.csv"
    source.write_text("source", encoding="utf-8")

    manifest = _input_manifest(tmp_path, {"parfumo": 1}, {"parfumo"})

    assert set(manifest) == {"parfumo_file"}
    assert manifest["parfumo_file"]["path"] == "parfumo_data_clean.csv"
