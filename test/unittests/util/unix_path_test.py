import os
import platform
import pytest

from conan.tools.microsoft.subsystems import subsystem_path
from conan.internal.subsystems import get_cased_path
from conan.test.utils.test_files import temp_folder
from conan.internal.util.files import mkdir


class TestGetCasedPath:
    @pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows")
    def test_case_existing(self):
        folder = get_cased_path(temp_folder())
        p1 = os.path.join(folder, "MyFolder", "Subfolder")
        mkdir(p1)

        assert p1 == get_cased_path(p1)  # Idempotent
        assert p1 == get_cased_path(os.path.join(folder, "myfolder", "subfolder"))

    def test_case_not_existing(self):
        current_dir = get_cased_path(os.getcwd())
        non_existing_path = os.path.join(current_dir, "this", "Path", "does", "NOT", "Exists")
        p = get_cased_path(non_existing_path)  # If not exists from the root, returns as is
        assert p == non_existing_path

    @pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows")
    def test_case_partial_exists(self):
        folder = get_cased_path(temp_folder())
        p1 = os.path.join(folder, "MyFolder", "Subfolder")
        mkdir(p1)

        non_existing_path = os.path.join(folder, "myfolder", "subfolder", "not-existing")
        # The first part of the path will be properly cased.
        assert os.path.join(p1, "not-existing") == get_cased_path(non_existing_path)


class TestUnixPath:

    def test_none(self):
        assert None == subsystem_path(None, path=None)

    def test_msys_path(self):
        assert '/c/windows/system32' == subsystem_path("msys2", 'C:\\Windows\\System32')

    def test_cygwin_path(self):
        assert '/cygdrive/c/windows/system32' == subsystem_path("cygwin",
                                                               'C:\\Windows\\System32')

        # another drive
        assert '/cygdrive/d/work' == subsystem_path("cygwin", "D:\\work")

        # path inside the cygwin
        assert '/home/.conan' == subsystem_path("cygwin", '/home/.conan')
        assert '/dev/null' == subsystem_path("cygwin", '/dev/null')

        # relative paths
        assert './configure' == subsystem_path("cygwin", './configure')
        assert '../configure' == subsystem_path("cygwin", '../configure')
        assert 'source_subfolder/configure' == subsystem_path("cygwin", 'source_subfolder/configure')

        assert './configure' == subsystem_path("cygwin", '.\\configure')
        assert '../configure' == subsystem_path("cygwin", '..\\configure')
        assert 'source_subfolder/configure' == subsystem_path("cygwin", 'source_subfolder\\configure')

        # already with cygdrive
        assert '/cygdrive/c/conan' == subsystem_path("cygwin", '/cygdrive/c/conan')

        # UNC (file share)
        assert '//server/share' == subsystem_path("cygwin", "\\\\SERVER\\Share")

        # long path
        assert '/cygdrive/c/windows/system32' == subsystem_path("cygwin", '\\\\?\\C:\\Windows\\System32')

    def test_wsl_path(self):
        assert '/mnt/c/Windows/System32' == subsystem_path("wsl", 'C:\\Windows\\System32')
