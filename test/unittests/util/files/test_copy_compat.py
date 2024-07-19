import pytest

from conans.util.files import copytree_compat


@pytest.fixture
def source_dest_folders(tmp_path):
    source_folder = tmp_path / "source"
    dest_folder = tmp_path / "dest"
    source_folder.mkdir()
    dest_folder.mkdir()
    test_file = source_folder / "test_file.txt"
    test_file.write_text("Test content")
    return source_folder, dest_folder


def test_copytree_compat(source_dest_folders):
    source_folder, dest_folder = source_dest_folders
    copytree_compat(str(source_folder), str(dest_folder))
    assert (dest_folder / "test_file.txt").exists()
