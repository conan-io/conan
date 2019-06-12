import os
import platform
import shutil
import tempfile
import unittest

from mock import mock
from parameterized import parameterized

from conans.client.cache.cache import ClientCache
from conans.client.tools.env import environment_append
from conans.model.ref import ConanFileReference, PackageReference
from conans.paths import BUILD_FOLDER, EXPORT_FOLDER, PACKAGES_FOLDER, conan_expand_user
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestBufferConanOutput
from conans.util.windows import path_shortener


class PathsTest(unittest.TestCase):

    def expand_user_test(self):
        if platform.system() == "Windows":
            old_env = dict(os.environ)
            try:
                os.environ["HOME"] = "%USERPROFILE%"
                user_home = conan_expand_user("~")
            finally:
                os.environ.clear()
                os.environ.update(old_env)
            self.assertTrue(os.path.exists(user_home))

    def basic_test(self):
        folder = temp_folder()
        paths = ClientCache(folder, TestBufferConanOutput())
        ref = ConanFileReference.loads("opencv/2.4.10@lasote/testing")
        pref = PackageReference(ref, "456fa678eae68")
        expected_base = os.path.join(folder, "data",
                                     os.path.sep.join(["opencv", "2.4.10",
                                                       "lasote", "testing"]))
        layout = paths.package_layout(ref)
        self.assertEqual(layout.base_folder(), expected_base)
        self.assertEqual(layout.export(),
                         os.path.join(expected_base, EXPORT_FOLDER))
        self.assertEqual(layout.build(pref),
                         os.path.join(expected_base, BUILD_FOLDER,  "456fa678eae68"))
        self.assertEqual(layout.package(pref),
                         os.path.join(expected_base, PACKAGES_FOLDER,
                                      "456fa678eae68"))


@mock.patch("subprocess.check_output", return_value=None)
class PathShortenerTest(unittest.TestCase):

    def run(self, *args, **kwargs):
        self.home_short = tempfile.mkdtemp(suffix='_home_short')
        self.home = tempfile.mkdtemp(suffix="_home")
        try:
            with environment_append({"CONAN_USER_HOME_SHORT": self.home_short,
                                     "USERNAME": "jgsogo"}):
                super(PathShortenerTest, self).run(*args, **kwargs)
        finally:
            shutil.rmtree(self.home_short, ignore_errors=True)
            shutil.rmtree(self.home, ignore_errors=True)

    @parameterized.expand([(False,), (True,)])
    @unittest.skipUnless(platform.system() == "Windows", "Requires windows")
    def test_default(self, _, short_paths):
        p = tempfile.mkdtemp(dir=self.home)
        r = path_shortener(path=p, short_paths=short_paths)

        self.assertEqual(self.home_short in r, short_paths)
        self.assertEqual(self.home in r, not short_paths)

    @parameterized.expand([(False,), (True,)])
    @unittest.skipUnless(platform.system() == "Windows", "Requires windows")
    def test_with_env_variable(self, _, short_paths):
        with environment_append({'CONAN_USE_ALWAYS_SHORT_PATHS': "True"}):
            p = tempfile.mkdtemp(dir=self.home)
            r = path_shortener(path=p, short_paths=short_paths)

            self.assertEqual(self.home_short in r, True)
            self.assertEqual(self.home in r, False)

        with environment_append({'CONAN_USE_ALWAYS_SHORT_PATHS': "False"}):
            p = tempfile.mkdtemp(dir=self.home)
            r = path_shortener(path=p, short_paths=short_paths)

            self.assertEqual(self.home_short in r, short_paths)
            self.assertEqual(self.home in r, not short_paths)

    @unittest.skipUnless(platform.system() == "Windows", "Requires windows")
    def test_path_is_different_for_different_files(self, _):
        p1 = tempfile.mkdtemp(dir=self.home)
        short1 = path_shortener(p1, True)
        p2 = tempfile.mkdtemp(dir=self.home)
        short2 = path_shortener(p2, True)

        self.assertNotEqual(short1, short2)

    @unittest.skipUnless(platform.system() == "Windows", "Requires windows")
    def test_path_is_deterministic(self, _):
        p = tempfile.mkdtemp(dir=self.home)
        short1 = path_shortener(p, True)
        short2 = path_shortener(p, True)

        self.assertEqual(short1, short2)

    @unittest.skipUnless(platform.system() == "Windows", "Requires windows")
    def test_path_is_relative_to_home_short(self, _):
        with environment_append({"CONAN_USER_HOME_SHORT": self.home_short}):
            p = tempfile.mkdtemp(dir=self.home)
            r = path_shortener(p, True)

        self.assertTrue(self.home_short in r)

@mock.patch("subprocess.check_output", return_value=None)
class PathShortenerWithTwoHomes(unittest.TestCase):
    def run(self, *args, **kwargs):
        self.home1 = tempfile.mkdtemp(suffix="_home")
        self.home2 = tempfile.mkdtemp(suffix="_home")
        self.home_short1 = tempfile.mkdtemp(suffix="_c")
        self.home_short2 = tempfile.mkdtemp(suffix="_c")
        self.file1 = os.path.join(self.home1, "testFile")
        self.file2 = os.path.join(self.home2, "testFile")

        try:
            with environment_append({"USERNAME": "jgsogo"}):
                super(PathShortenerWithTwoHomes, self).run(*args, **kwargs)
        finally:
            for f in (self.home1, self.home2, self.home_short1, self.home_short2):
                shutil.rmtree(f, ignore_errors=True)

    @unittest.skipUnless(platform.system() == "Windows", "Requires windows")
    def test_path_is_not_the_same_for_different_homes(self, _):
        with environment_append({"CONAN_USER_HOME": self.home1}):
            short1 = path_shortener(self.file1, True)

        with environment_append({"CONAN_USER_HOME": self.home2}):
            short2 = path_shortener(self.file2, True)

        self.assertNotEqual(short1, short2)

    # This test case is important for CI setups with folder-based isolation of
    # conan homes and compiler caches.
    @unittest.skipUnless(platform.system() == "Windows", "Requires windows")
    def test_path_is_deterministic_relatively_to_home_short_with_different_homes(self, _):
        with environment_append({"CONAN_USER_HOME": self.home1,
                                 "CONAN_USER_HOME_SHORT": self.home_short1}):
            short1 = path_shortener(self.file1, True)

        with environment_append({"CONAN_USER_HOME": self.home2,
                                 "CONAN_USER_HOME_SHORT": self.home_short2}):
            short2 = path_shortener(self.file2, True)

        self.assertEqual(short1[len(self.home_short1):], short2[len(self.home_short2):])
