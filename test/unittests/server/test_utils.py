import os

from conans.server.utils.files import path_exists
from conan.test.utils.test_files import temp_folder
from conans.util.files import mkdir


def test_path_exists():
    """
    Unit test of path_exists
    """
    tmp_dir = temp_folder()
    tmp_dir = os.path.join(tmp_dir, "WhatEver")
    new_path = os.path.join(tmp_dir, "CapsDir")
    mkdir(new_path)
    assert path_exists(new_path, tmp_dir)
    assert not path_exists(os.path.join(tmp_dir, "capsdir"), tmp_dir)
