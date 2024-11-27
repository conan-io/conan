import os
import platform
import unittest

import pytest

from conan.tools.microsoft.subsystems import subsystem_path
from conans.client.subsystems import get_cased_path
from conan.test.utils.test_files import temp_folder
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
        self.assertEqual(None, subsystem_path(None, path=None))

    def test_msys_path(self):
        self.assertEqual('/c/windows/system32', subsystem_path("msys2", 'C:\\Windows\\System32'))

    def test_cygwin_path(self):
        self.assertEqual('/cygdrive/c/windows/system32', subsystem_path("cygwin",
                                                                        'C:\\Windows\\System32'))

        # another drive
        self.assertEqual('/cygdrive/d/work', subsystem_path("cygwin", "D:\\work"))

        # path inside the cygwin
        self.assertEqual('/home/.conan', subsystem_path("cygwin", '/home/.conan'))
        self.assertEqual('/dev/null', subsystem_path("cygwin", '/dev/null'))

        # relative paths
        self.assertEqual('./configure', subsystem_path("cygwin", './configure'))
        self.assertEqual('../configure', subsystem_path("cygwin", '../configure'))
        self.assertEqual('source_subfolder/configure',
                         subsystem_path("cygwin", 'source_subfolder/configure'))

        self.assertEqual('./configure', subsystem_path("cygwin", '.\\configure'))
        self.assertEqual('../configure', subsystem_path("cygwin", '..\\configure'))
        self.assertEqual('source_subfolder/configure',
                         subsystem_path("cygwin", 'source_subfolder\\configure'))

        # already with cygdrive
        self.assertEqual('/cygdrive/c/conan',
                         subsystem_path("cygwin", '/cygdrive/c/conan'))

        # UNC (file share)
        self.assertEqual('//server/share',
                         subsystem_path("cygwin", "\\\\SERVER\\Share"))

        # long path
        self.assertEqual('/cygdrive/c/windows/system32',
                         subsystem_path("cygwin", '\\\\?\\C:\\Windows\\System32'))

    def test_wsl_path(self):
        self.assertEqual('/mnt/c/Windows/System32', subsystem_path("wsl", 'C:\\Windows\\System32'))
