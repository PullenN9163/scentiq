import hashlib
import io
import json
import zipfile
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.request import Request

import pytest

from scentiq_api import dataset_refresh
from scentiq_api.dataset_refresh import (
    ARCHIVE_NAME,
    MANIFEST_NAME,
    DatasetRefreshError,
    main,
    refresh,
)

METADATA_URL = "https://www.kaggle.com/api/v1/datasets/view/ledecanteur/fragrantica-perfumes"
DOWNLOAD_URL = (
    "https://www.kaggle.com/api/v1/datasets/download/ledecanteur/fragrantica-perfumes"
    "?datasetVersionNumber={version}"
)
FIXED_NOW = datetime(2026, 9, 28, 6, 17, tzinfo=UTC)


def _record(perfume_id: int, **overrides: object) -> dict[str, object]:
    return {"id": perfume_id, "name": f"Perfume {perfume_id}", "brand": "House"} | overrides


def _archive(
    records: list[dict[str, object]] | None = None,
    members: Mapping[str, bytes] | None = None,
) -> bytes:
    if members is None:
        lines = "\n".join(json.dumps(record) for record in (records or [_record(1)]))
        members = {
            "perfumes.jsonl": (lines + "\n").encode(),
            "perfumes.csv": b"id,name,brand\n1,Perfume 1,House\n",
            "SCHEMA.md": b"# Schema\n",
        }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def _metadata(version: object = 4) -> bytes:
    return json.dumps(
        {
            "currentVersionNumber": version,
            "lastUpdated": "2026-09-27T07:00:00.000Z",
            "licenseName": "CC BY-NC-SA 4.0",
        }
    ).encode()


class FakeKaggle:
    def __init__(self, responses: Mapping[str, bytes]) -> None:
        self.responses = dict(responses)
        self.requested: list[str] = []

    @contextmanager
    def __call__(self, request: Request) -> Iterator[io.BytesIO]:
        self.requested.append(request.full_url)
        yield io.BytesIO(self.responses[request.full_url])


def _kaggle(archive: bytes | None = None, version: int = 4) -> FakeKaggle:
    responses = {METADATA_URL: _metadata(version)}
    if archive is not None:
        responses[DOWNLOAD_URL.format(version=version)] = archive
    return FakeKaggle(responses)


def _run(
    kaggle: FakeKaggle, output_dir: Path, manifest: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    return refresh(manifest, output_dir, opener=kaggle, now=lambda: FIXED_NOW)


def test_an_unchanged_version_downloads_nothing(tmp_path: Path) -> None:
    kaggle = _kaggle(version=3)

    summary = _run(kaggle, tmp_path / "out", {"version": 3, "record_count": 10})

    assert summary == {"changed": False, "stored_version": 3, "published_version": 3}
    assert kaggle.requested == [METADATA_URL]
    assert not (tmp_path / "out").exists()


def test_a_newer_version_is_downloaded_pinned_validated_and_described(tmp_path: Path) -> None:
    archive = _archive([_record(1), _record(2), _record(3)])
    kaggle = _kaggle(archive, version=4)
    output_dir = tmp_path / "out"

    summary = _run(kaggle, output_dir, {"version": 3, "record_count": 3})

    assert kaggle.requested == [METADATA_URL, DOWNLOAD_URL.format(version=4)]
    assert (output_dir / ARCHIVE_NAME).read_bytes() == archive
    manifest = json.loads((output_dir / MANIFEST_NAME).read_text(encoding="utf-8"))
    assert manifest == {
        "source": "kaggle",
        "dataset": "ledecanteur/fragrantica-perfumes",
        "version": 4,
        "published_at": "2026-09-27T07:00:00.000Z",
        "license": "CC BY-NC-SA 4.0",
        "retrieved_at": "2026-09-28T06:17:00+00:00",
        "archive_blob": "fragrantica/v4/fragrantica-perfumes.zip",
        "manifest_blob": "fragrantica/v4/manifest.json",
        "sha256": hashlib.sha256(archive).hexdigest(),
        "bytes": len(archive),
        "record_count": 3,
    }
    assert summary == {"changed": True, **manifest}


def test_the_first_run_stores_whatever_version_is_published(tmp_path: Path) -> None:
    summary = _run(_kaggle(_archive(), version=3), tmp_path / "out", None)

    assert summary["changed"] is True
    assert summary["version"] == 3
    assert summary["record_count"] == 1


def test_members_nested_in_a_folder_are_accepted(tmp_path: Path) -> None:
    lines = json.dumps(_record(1)).encode()
    archive = _archive(
        members={
            "release/perfumes.jsonl": lines,
            "release/perfumes.csv": b"id\n1\n",
            "release/SCHEMA.md": b"# Schema\n",
        }
    )

    assert _run(_kaggle(archive), tmp_path / "out")["record_count"] == 1


@pytest.mark.parametrize(
    ("archive", "reason"),
    [
        pytest.param(
            _archive(members={"perfumes.jsonl": b"{}", "SCHEMA.md": b"#"}),
            "missing perfumes.csv",
            id="missing-member",
        ),
        pytest.param(
            _archive([_record(1), _record(2, brand="")]),
            "line 2 has no brand",
            id="record-without-brand",
        ),
        pytest.param(
            _archive(
                members={"perfumes.jsonl": b"not json\n", "perfumes.csv": b"", "SCHEMA.md": b""}
            ),
            "line 1 is not JSON",
            id="malformed-record",
        ),
        pytest.param(
            _archive(members={"perfumes.jsonl": b"\n", "perfumes.csv": b"", "SCHEMA.md": b""}),
            "contains no records",
            id="empty-release",
        ),
        pytest.param(b"this is not a zip", "not a valid zip", id="corrupt-archive"),
    ],
)
def test_an_invalid_release_is_rejected_and_leaves_no_archive(
    archive: bytes, reason: str, tmp_path: Path
) -> None:
    output_dir = tmp_path / "out"

    with pytest.raises(DatasetRefreshError, match=reason):
        _run(_kaggle(archive), output_dir, {"version": 3})

    assert not (output_dir / ARCHIVE_NAME).exists()
    assert not (output_dir / MANIFEST_NAME).exists()


def test_a_release_that_loses_too_many_records_is_rejected(tmp_path: Path) -> None:
    archive = _archive([_record(index) for index in range(1, 9)])

    with pytest.raises(DatasetRefreshError, match="fell from 10 to 8"):
        _run(_kaggle(archive), tmp_path / "out", {"version": 3, "record_count": 10})

    assert not (tmp_path / "out" / ARCHIVE_NAME).exists()


def test_a_small_decline_in_records_is_accepted(tmp_path: Path) -> None:
    archive = _archive([_record(index) for index in range(1, 10)])

    summary = _run(_kaggle(archive), tmp_path / "out", {"version": 3, "record_count": 10})

    assert summary["record_count"] == 9


@pytest.mark.parametrize("version", [None, "4", 0, True])
def test_metadata_without_a_usable_version_is_rejected(version: object, tmp_path: Path) -> None:
    kaggle = FakeKaggle({METADATA_URL: _metadata(version)})

    with pytest.raises(DatasetRefreshError, match="no valid current version"):
        _run(kaggle, tmp_path / "out")

    assert kaggle.requested == [METADATA_URL]


def test_the_command_reads_a_missing_manifest_as_nothing_stored(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output_dir = tmp_path / "out"

    exit_code = main(
        ["--current-manifest", str(tmp_path / "absent.json"), "--output-dir", str(output_dir)],
        opener=_kaggle(_archive(), version=3),
    )

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out)["version"] == 3
    assert (output_dir / ARCHIVE_NAME).exists()


def test_the_command_reports_an_unchanged_version(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    manifest_path = tmp_path / "latest.json"
    manifest_path.write_text(json.dumps({"version": 3, "record_count": 1}), encoding="utf-8")

    exit_code = main(
        ["--current-manifest", str(manifest_path), "--output-dir", str(tmp_path / "out")],
        opener=_kaggle(version=3),
    )

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out)["changed"] is False


def test_the_command_exits_non_zero_on_a_rejected_release(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(
        ["--output-dir", str(tmp_path / "out")],
        opener=_kaggle(b"this is not a zip", version=3),
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert "Dataset refresh rejected: archive is not a valid zip file" in captured.err


def test_the_default_opener_sets_a_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, float]] = []

    def fake_urlopen(request: Request, timeout: float) -> io.BytesIO:
        calls.append((request.full_url, timeout))
        return io.BytesIO(b"")

    monkeypatch.setattr(dataset_refresh, "urlopen", fake_urlopen)

    with dataset_refresh._open(dataset_refresh._request(METADATA_URL)):
        pass

    assert calls == [(METADATA_URL, dataset_refresh.REQUEST_TIMEOUT_SECONDS)]
