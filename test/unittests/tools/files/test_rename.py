import os
import platform
import pytest

from conan.tools.files import rename
from conan.test.utils.mocks import ConanFileMock
from conan.test.utils.tools import temp_folder, save_files


def test_rename_file():
    conanfile = ConanFileMock()
    tmp = temp_folder()
    save_files(tmp, {"file.txt": ""})
    old_path = os.path.join(tmp, "file.txt")
    new_path = os.path.join(tmp, "kk.txt")
    rename(conanfile, old_path, new_path)
    assert not os.path.exists(old_path)
    assert os.path.exists(new_path)


@pytest.mark.skipif(platform.system() != "Windows", reason="Robocopy only exists in Windows")
def test_rename_folder_robocopy():
    conanfile = ConanFileMock()
    tmp = temp_folder()
    old_folder = os.path.join(tmp, "old_folder")
    os.mkdir(old_folder)
    new_folder = os.path.join(tmp, "new_folder")
    rename(conanfile, old_folder, new_folder)
    assert not os.path.exists(old_folder)
    assert os.path.exists(new_folder)
