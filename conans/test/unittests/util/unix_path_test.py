import mock
import os
import platform
import unittest

import pytest

from conans.client import tools
from conans.client.tools.win import get_cased_path
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
        self.assertEqual(None, tools.unix_path(path=None))

    @mock.patch("platform.system", mock.MagicMock(return_value='Darwin'))
    def test_not_windows(self):
        path = 'C:\\Windows\\System32'
        self.assertEqual(path, tools.unix_path(path))

    @mock.patch("platform.system", mock.MagicMock(return_value='Windows'))
    def test_msys_path(self):
        self.assertEqual('/c/windows/system32', tools.unix_path('C:\\Windows\\System32',
                                                                path_flavor=tools.MSYS2))

    @mock.patch("platform.system", mock.MagicMock(return_value='Windows'))
    def test_cygwin_path(self):
        self.assertEqual('/cygdrive/c/windows/system32', tools.unix_path('C:\\Windows\\System32',
                                                                         path_flavor=tools.CYGWIN))

        # another drive
        self.assertEqual('/cygdrive/d/work', tools.unix_path("D:\\work", path_flavor=tools.CYGWIN))

        # path inside the cygwin
        self.assertEqual('/home/.conan', tools.unix_path('/home/.conan', path_flavor=tools.CYGWIN))
        self.assertEqual('/dev/null', tools.unix_path('/dev/null', path_flavor=tools.CYGWIN))

        # relative paths
        self.assertEqual('./configure', tools.unix_path('./configure', path_flavor=tools.CYGWIN))
        self.assertEqual('../configure', tools.unix_path('../configure', path_flavor=tools.CYGWIN))
        self.assertEqual('source_subfolder/configure',
                         tools.unix_path('source_subfolder/configure', path_flavor=tools.CYGWIN))

        self.assertEqual('./configure', tools.unix_path('.\\configure', path_flavor=tools.CYGWIN))
        self.assertEqual('../configure', tools.unix_path('..\\configure', path_flavor=tools.CYGWIN))
        self.assertEqual('source_subfolder/configure',
                         tools.unix_path('source_subfolder\\configure', path_flavor=tools.CYGWIN))

        # already with cygdrive
        self.assertEqual('/cygdrive/c/conan',
                         tools.unix_path('/cygdrive/c/conan', path_flavor=tools.CYGWIN))

        # UNC (file share)
        self.assertEqual('//server/share',
                         tools.unix_path("\\\\SERVER\\Share", path_flavor=tools.CYGWIN))

        # long path
        self.assertEqual('/cygdrive/c/windows/system32',
                         tools.unix_path('\\\\?\\C:\\Windows\\System32', path_flavor=tools.CYGWIN))

    @mock.patch("platform.system", mock.MagicMock(return_value='Windows'))
    def test_wsl_path(self):
        self.assertEqual('/mnt/c/Windows/System32', tools.unix_path('C:\\Windows\\System32',
                                                                    path_flavor=tools.WSL))

    @mock.patch("platform.system", mock.MagicMock(return_value='Windows'))
    def test_sfu_path(self):
        self.assertEqual('/dev/fs/C/windows/system32', tools.unix_path('C:\\Windows\\System32',
                                                                       path_flavor=tools.SFU))
