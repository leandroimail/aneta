import os

from src.StorageReport import measure


def test_distinguishes_hardlinks_and_copies(tmp_path):
    source = tmp_path / ".hidden"
    source.mkdir()
    data = source / "first"
    data.write_bytes(b"shared")
    os.link(data, tmp_path / "link")
    (tmp_path / "copy").write_bytes(data.read_bytes())
    (tmp_path / "pointer").symlink_to(data)
    result = measure([tmp_path])
    assert result["duplicate_logical_bytes"] == 6
    assert sum(result["allocated_bytes_by_directory"].values()) == 2 * data.stat().st_blocks * 512
