import mock
import os
import platform
import unittest

import pytest

from conan.tools.microsoft import unix_path
from conan.tools.microsoft.subsystems import get_cased_path
from conans.test.utils.mocks import ConanFileMock
from conans.test.utils.test_files import temp_folder
from conans.util.files import mkdir


class GetCasedPath(unittest.TestCase):
    @pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows")
    def test_case_existing(self):
        folder = get_cased_path(temp_folder())
        p1 = os.path.join(folder, "MyFolder", "Subfolder")
        mkdir(p1)

        self.assertEqual(p1, get_cased_path(p1))  # Idempotent
        self.assertEqual(p1, get_cased_path(os.path.join(folder, "myfolder", "subfolder")))

    def test_case_not_existing(self):
        current_dir = get_cased_path(os.getcwd())
        non_existing_path = os.path.join(current_dir, "this", "Path", "does", "NOT", "Exists")
        p = get_cased_path(non_existing_path)  # If not exists from the root, returns as is
        self.assertEqual(p, non_existing_path)

    @pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows")
    def test_case_partial_exists(self):
        folder = get_cased_path(temp_folder())
        p1 = os.path.join(folder, "MyFolder", "Subfolder")
        mkdir(p1)

        non_existing_path = os.path.join(folder, "myfolder", "subfolder", "not-existing")
        # The first part of the path will be properly cased.
        self.assertEqual(os.path.join(p1, "not-existing"),
                         get_cased_path(non_existing_path))


class UnixPathTest(unittest.TestCase):

    def test_none(self):
        conanfile = ConanFileMock()
        self.assertEqual(None, unix_path(conanfile, path=None))

    @mock.patch("platform.system", mock.MagicMock(return_value='Darwin'))
    def test_not_windows(self):
        path = 'C:\\Windows\\System32'
        conanfile = ConanFileMock()
        self.assertEqual(path, unix_path(conanfile, path))

    @mock.patch("platform.system", mock.MagicMock(return_value='Windows'))
    def test_msys_path(self):
        conanfile = ConanFileMock()
        conanfile.win_bash = True
        conanfile.conf["tools.microsoft.bash:subsystem"] = "msys2"
        self.assertEqual('/c/windows/system32', unix_path(conanfile, 'C:\\Windows\\System32'))

    @mock.patch("platform.system", mock.MagicMock(return_value='Windows'))
    def test_cygwin_path(self):
        conanfile = ConanFileMock()
        conanfile.win_bash = True
        conanfile.conf["tools.microsoft.bash:subsystem"] = "cygwin"
        self.assertEqual('/cygdrive/c/windows/system32', unix_path(conanfile, 'C:\\Windows\\System32'))

        # another drive
        self.assertEqual('/cygdrive/d/work', unix_path(conanfile, "D:\\work"))

        # path inside the cygwin
        self.assertEqual('/home/.conan', unix_path(conanfile, '/home/.conan'))
        self.assertEqual('/dev/null', unix_path(conanfile, '/dev/null'))

        # relative paths
        self.assertEqual('./configure', unix_path(conanfile, './configure'))
        self.assertEqual('../configure', unix_path(conanfile, '../configure'))
        self.assertEqual('source_subfolder/configure',
                         unix_path(conanfile, 'source_subfolder/configure'))

        self.assertEqual('./configure', unix_path(conanfile, '.\\configure'))
        self.assertEqual('../configure', unix_path(conanfile, '..\\configure'))
        self.assertEqual('source_subfolder/configure',
                         unix_path(conanfile, 'source_subfolder\\configure'))

        # already with cygdrive
        self.assertEqual('/cygdrive/c/conan',
                         unix_path(conanfile, '/cygdrive/c/conan'))

        # UNC (file share)
        self.assertEqual('//server/share',
                         unix_path(conanfile, "\\\\SERVER\\Share"))

        # long path
        self.assertEqual('/cygdrive/c/windows/system32',
                         unix_path(conanfile, '\\\\?\\C:\\Windows\\System32'))

    @mock.patch("platform.system", mock.MagicMock(return_value='Windows'))
    def test_wsl_path(self):
        conanfile = ConanFileMock()
        conanfile.win_bash = True
        conanfile.conf["tools.microsoft.bash:subsystem"] = "wsl"
        self.assertEqual('/mnt/c/Windows/System32', unix_path(conanfile, 'C:\\Windows\\System32'))

    @mock.patch("platform.system", mock.MagicMock(return_value='Windows'))
    def test_sfu_path(self):
        conanfile = ConanFileMock()
        conanfile.win_bash = True
        conanfile.conf["tools.microsoft.bash:subsystem"] = "sfu"
        self.assertEqual('/dev/fs/C/windows/system32', unix_path(conanfile, 'C:\\Windows\\System32'))
