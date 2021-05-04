import os
import pytest

from conan.tools.files import rename
from conans.test.utils.mocks import ConanFileMock
from conans.test.utils.tools import TestClient


def test_single_patch_file():
    conanfile = ConanFileMock()
    client = TestClient()
    client.save({"file.txt": ""})
    old_path = os.path.join(client.current_folder, "file.txt")
    new_path = os.path.join(client.current_folder, "kk.txt")
    rename(conanfile, old_path, new_path)
    assert not os.path.exists(old_path)
    assert os.path.exists(new_path)
