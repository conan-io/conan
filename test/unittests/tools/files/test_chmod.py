import os
import platform
import stat
import pytest

from conan.errors import ConanException
from conan.tools.files import chmod
from conan.test.utils.mocks import ConanFileMock
from conan.test.utils.tools import temp_folder, save_files


@pytest.mark.skipif(platform.system() == "Windows", reason="validate full permissions only in Unix")
@pytest.mark.parametrize("read,write,execute,expected", [
    (True, True, True, 0o700),
    (False, True, False, 0o200),
    (False, False, True, 0o100),
    (True, False, True, 0o500),
    (True, True, False, 0o600),
    (True, False, False, 0o400),
    (False, False, False, 0o000),])
def test_chmod_single_file(read, write, execute, expected):
    """
    The chmod should be able to change the permissions of a single file.
    """
    tmp = temp_folder()
    save_files(tmp, {"file.txt": "foobar"})
    file_path = os.path.join(tmp, "file.txt")
    os.chmod(file_path, 0o000)
    conanfile = ConanFileMock()
    chmod(conanfile, file_path, read=read, write=write, execute=execute, recursive=False)
    file_mode = os.stat(file_path).st_mode
    assert stat.S_IMODE(file_mode) == expected


@pytest.mark.skipif(platform.system() == "Windows", reason="validate full permissions only in Unix")
@pytest.mark.parametrize("read,write,execute,expected", [
    (True, True, True, 0o700),
    (False, True, False, 0o200),
    (False, False, True, 0o100),
    (True, False, True, 0o500),
    (True, True, False, 0o600),
    (True, False, False, 0o400),
    (False, False, False, 0o000),])
def test_chmod_recursive(read, write, execute, expected):
    """
    The chmod should be able to change the permissions of all files in a folder when recursive is set to True.
    """
    tmp = temp_folder()
    files = {"foobar/qux/file.txt": "foobar",
             "foobar/file.txt": "qux",
             "foobar/foo/file.txt": "foobar"}
    save_files(tmp, files)
    folder_path = os.path.join(tmp, "foobar")
    for file in files.keys():
        file_path = os.path.join(tmp, file)
        os.chmod(file_path, 0o000)
    conanfile = ConanFileMock()
    chmod(conanfile, folder_path, read=read, write=write, execute=execute, recursive=True)
    for file in files.keys():
        file_mode = os.stat(os.path.join(tmp, file)).st_mode
        assert stat.S_IMODE(file_mode) == expected


@pytest.mark.skipif(platform.system() == "Windows", reason="Validate default permissions only in Unix")
def test_chmod_default_values():
    """
    When not passing a permission parameter, chmod should not change the specific permission.
    """
    tmp = temp_folder()
    save_files(tmp, {"file.txt": "foobar"})
    file_path = os.path.join(tmp, "file.txt")
    os.chmod(file_path, 0o111)
    conanfile = ConanFileMock()
    chmod(conanfile, file_path, read=True)
    file_mode = os.stat(file_path).st_mode
    assert stat.S_IMODE(file_mode) == 0o511


def test_missing_permission_arguments():
    """
    The chmod should raise an exception if no new permission is provided.
    """
    conanfile = ConanFileMock()
    with pytest.raises(ConanException) as error:
        chmod(conanfile, "invalid_path")
    assert 'Could not change permission: At least one of the permissions should be set.' in str(error.value)


def test_invalid_path():
    """
    The chmod should raise an exception if the path does not exist.
    """
    conanfile = ConanFileMock()
    with pytest.raises(ConanException) as error:
        chmod(conanfile, "invalid_path", read=True, write=True, execute=True, recursive=False)
    assert 'Could not change permission: Path "invalid_path" does not exist.' in str(error.value)


@pytest.mark.skipif(platform.system() != "Windows", reason="Validate read-only permissions only in Windows")
def test_chmod_windows():
    """
    The chmod should be able to change read-only state in Windows.
    """
    tmp = temp_folder()
    save_files(tmp, {"file.txt": "foobar"})
    file_path = os.path.join(tmp, "file.txt")
    os.chmod(file_path, 0o000)
    conanfile = ConanFileMock()
    chmod(conanfile, file_path, read=True, write=True, execute=True, recursive=False)
    assert os.access(file_path, os.W_OK)
