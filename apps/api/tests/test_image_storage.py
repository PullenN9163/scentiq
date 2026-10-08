from pathlib import Path

import pytest

from scentiq_api.storage.images import LocalImageStorage


def test_failed_atomic_replace_preserves_previous_image(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    storage = LocalImageStorage(tmp_path)
    storage.write("users/owner/fragrances/item/image.webp", b"previous")

    def fail_replace(self: Path, target: Path) -> None:
        raise OSError("disk unavailable")

    monkeypatch.setattr(Path, "replace", fail_replace)
    with pytest.raises(OSError):
        storage.write("users/owner/fragrances/item/image.webp", b"replacement")
    assert storage.read("users/owner/fragrances/item/image.webp") == b"previous"
    assert not list(tmp_path.rglob("*.tmp"))
