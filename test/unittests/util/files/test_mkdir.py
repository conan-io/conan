import os
import pytest
from conan.errors import ConanException
from conan.test.utils.test_files import temp_folder
from conan.internal.util.files import mkdir, save


def test_create_folder_with_same_file_name():
    tmpdir = temp_folder()

    save(os.path.join(tmpdir, "build"), "content")
    with pytest.raises(ConanException, match="Path already exists and is not a folder"):
        mkdir(os.path.join(tmpdir, "build"))

    mkdir(os.path.join(tmpdir, "build_folder"))
    mkdir(os.path.join(tmpdir, "build_folder", "build_folder2"))

    assert os.path.isfile(os.path.join(tmpdir, "build"))
    assert os.path.isdir(os.path.join(tmpdir, "build_folder"))
    assert os.path.isdir(os.path.join(tmpdir, "build_folder", "build_folder2"))
