"""Scheduled refresh of the Fragrantica catalogue dataset published on Kaggle.

Compares the dataset's published Kaggle version with the manifest of the copy
already stored and, when Kaggle has a newer one, downloads and validates it:

    uv run --directory apps/api python -m scentiq_api.dataset_refresh \\
        --current-manifest latest.json --output-dir dataset

Prints a JSON summary. When a newer version passes validation, the output
directory holds the archive and its manifest, ready for upload; otherwise it
is left without an archive. Nothing is uploaded here: storage writes belong to
the calling workflow, so this module needs no Azure credentials and can be
exercised offline.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, cast
from urllib.request import Request, urlopen

DATASET_REF = "ledecanteur/fragrantica-perfumes"
KAGGLE_API_URL = "https://www.kaggle.com/api/v1"
BLOB_PREFIX = "fragrantica"
ARCHIVE_NAME = "fragrantica-perfumes.zip"
MANIFEST_NAME = "manifest.json"
RECORDS_MEMBER = "perfumes.jsonl"
REQUIRED_MEMBERS = frozenset({RECORDS_MEMBER, "perfumes.csv", "SCHEMA.md"})
REQUIRED_RECORD_FIELDS = ("id", "name", "brand")
# A release that loses more than this share of the stored record count is far
# more likely to be a broken upload than a genuine catalogue change.
MAX_RECORD_DROP = 0.10
REQUEST_TIMEOUT_SECONDS = 60
_CHUNK_BYTES = 1024 * 1024


class _Response(Protocol):
    def read(self, size: int = -1, /) -> bytes: ...


Opener = Callable[[Request], AbstractContextManager[_Response]]


class DatasetRefreshError(Exception):
    """The published dataset could not be retrieved or failed validation."""


@dataclass(frozen=True)
class Release:
    version: int
    published_at: str
    license_name: str


def _open(request: Request) -> AbstractContextManager[_Response]:
    return cast(
        AbstractContextManager[_Response], urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS)
    )


def _request(url: str) -> Request:
    return Request(url, headers={"User-Agent": "scentiq-dataset-refresh"})


def parse_release(payload: Mapping[str, Any]) -> Release:
    version = payload.get("currentVersionNumber")
    # bool is an int subclass; a true/false version is malformed, not version 1.
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise DatasetRefreshError("Kaggle metadata has no valid current version number")
    published_at = payload.get("lastUpdated")
    license_name = payload.get("licenseName")
    return Release(
        version=version,
        published_at=published_at if isinstance(published_at, str) else "",
        license_name=license_name if isinstance(license_name, str) else "",
    )


def fetch_release(opener: Opener = _open, dataset_ref: str = DATASET_REF) -> Release:
    with opener(_request(f"{KAGGLE_API_URL}/datasets/view/{dataset_ref}")) as response:
        payload = json.loads(response.read())
    if not isinstance(payload, dict):
        raise DatasetRefreshError("Kaggle metadata was not a JSON object")
    return parse_release(payload)


def read_manifest(path: Path | None) -> dict[str, Any] | None:
    """Return the stored manifest, or None when no copy has been stored yet."""
    if path is None or not path.exists():
        return None
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise DatasetRefreshError("the stored manifest is not a JSON object")
    return manifest


def download_archive(
    version: int, destination: Path, opener: Opener = _open, dataset_ref: str = DATASET_REF
) -> tuple[str, int]:
    """Download one pinned version, returning its SHA-256 and size in bytes.

    Pinning the version keeps the archive consistent with the metadata that was
    checked, even if the maintainer publishes again mid-run.
    """
    url = f"{KAGGLE_API_URL}/datasets/download/{dataset_ref}?datasetVersionNumber={version}"
    digest = hashlib.sha256()
    size = 0
    with opener(_request(url)) as response, destination.open("wb") as archive:
        while chunk := response.read(_CHUNK_BYTES):
            digest.update(chunk)
            archive.write(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def count_valid_records(archive_path: Path) -> int:
    """Validate the archive's contents and return its perfume record count.

    Every member is read in full, so a truncated or corrupt archive fails its
    CRC check here rather than after upload.
    """
    try:
        with zipfile.ZipFile(archive_path) as archive:
            members = {Path(name).name: name for name in archive.namelist()}
            missing = sorted(REQUIRED_MEMBERS - members.keys())
            if missing:
                raise DatasetRefreshError(f"archive is missing {', '.join(missing)}")

            for member in sorted(set(archive.namelist()) - {members[RECORDS_MEMBER]}):
                with archive.open(member) as stream:
                    while stream.read(_CHUNK_BYTES):
                        pass

            records = 0
            with archive.open(members[RECORDS_MEMBER]) as stream:
                for line_number, line in enumerate(stream, start=1):
                    if not line.strip():
                        continue
                    _validate_record(line, line_number)
                    records += 1
            return records
    except zipfile.BadZipFile as error:
        raise DatasetRefreshError(f"archive is not a valid zip file: {error}") from error


def _validate_record(line: bytes, line_number: int) -> None:
    # Errors cite line numbers only; record content is third-party data and
    # does not belong in workflow logs.
    try:
        record = json.loads(line)
    except json.JSONDecodeError as error:
        raise DatasetRefreshError(f"{RECORDS_MEMBER} line {line_number} is not JSON") from error
    if not isinstance(record, dict):
        raise DatasetRefreshError(f"{RECORDS_MEMBER} line {line_number} is not an object")
    for field in REQUIRED_RECORD_FIELDS:
        if record.get(field) in (None, ""):
            raise DatasetRefreshError(f"{RECORDS_MEMBER} line {line_number} has no {field}")


def check_record_count(records: int, previous_records: object) -> None:
    if records == 0:
        raise DatasetRefreshError(f"{RECORDS_MEMBER} contains no records")
    if isinstance(previous_records, int) and not isinstance(previous_records, bool):
        floor = previous_records * (1 - MAX_RECORD_DROP)
        if records < floor:
            raise DatasetRefreshError(
                f"record count fell from {previous_records} to {records}, "
                f"more than the {MAX_RECORD_DROP:.0%} allowed"
            )


def refresh(
    current_manifest: Mapping[str, Any] | None,
    output_dir: Path,
    opener: Opener = _open,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> dict[str, Any]:
    release = fetch_release(opener)
    stored_version = current_manifest.get("version") if current_manifest else None
    if isinstance(stored_version, int) and release.version <= stored_version:
        return {
            "changed": False,
            "stored_version": stored_version,
            "published_version": release.version,
        }

    output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = output_dir / ARCHIVE_NAME
    try:
        sha256, size = download_archive(release.version, archive_path, opener)
        records = count_valid_records(archive_path)
        check_record_count(
            records, current_manifest.get("record_count") if current_manifest else None
        )
    except BaseException:
        # Leave nothing behind that the workflow could mistake for a good copy.
        archive_path.unlink(missing_ok=True)
        raise

    version_prefix = f"{BLOB_PREFIX}/v{release.version}"
    manifest = {
        "source": "kaggle",
        "dataset": DATASET_REF,
        "version": release.version,
        "published_at": release.published_at,
        "license": release.license_name,
        "retrieved_at": now().isoformat(),
        "archive_blob": f"{version_prefix}/{ARCHIVE_NAME}",
        "manifest_blob": f"{version_prefix}/{MANIFEST_NAME}",
        "sha256": sha256,
        "bytes": size,
        "record_count": records,
    }
    (output_dir / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2) + "\n", "utf-8")
    return {"changed": True, **manifest}


def _parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download and validate a newer Kaggle release of the Fragrantica dataset",
    )
    parser.add_argument(
        "--current-manifest",
        type=Path,
        help="Manifest of the stored copy; a missing file means nothing is stored yet",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Where a newer, validated archive and its manifest are written",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None, opener: Opener = _open) -> int:
    arguments = _parse_arguments(argv)
    try:
        summary = refresh(read_manifest(arguments.current_manifest), arguments.output_dir, opener)
    except DatasetRefreshError as error:
        print(f"Dataset refresh rejected: {error}", file=sys.stderr)
        return 1
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
