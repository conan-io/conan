import os
import platform
import unittest
import tempfile
import shutil
from parameterized import parameterized
from mock import mock

from conans.paths import (BUILD_FOLDER, PACKAGES_FOLDER, EXPORT_FOLDER, conan_expand_user,
                          SimplePaths)
from conans.model.ref import ConanFileReference, PackageReference
from conans.test.utils.test_files import temp_folder
from conans.client.tools.env import environment_append
from conans.client.tools.files import save
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
        paths = SimplePaths(folder)
        self.assertEqual(paths._store_folder, folder)
        conan_ref = ConanFileReference.loads("opencv/2.4.10 @ lasote /testing")
        package_ref = PackageReference(conan_ref, "456fa678eae68")
        expected_base = os.path.join(folder, os.path.sep.join(["opencv", "2.4.10",
                                                               "lasote", "testing"]))
        self.assertEqual(paths.conan(conan_ref),
                         os.path.join(paths.store, expected_base))
        self.assertEqual(paths.export(conan_ref),
                         os.path.join(paths.store, expected_base, EXPORT_FOLDER))
        self.assertEqual(paths.build(package_ref),
                         os.path.join(paths.store, expected_base, BUILD_FOLDER,  "456fa678eae68"))
        self.assertEqual(paths.package(package_ref),
                         os.path.join(paths.store, expected_base, PACKAGES_FOLDER,
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
    def test_default(self, _, short_paths):
        p = tempfile.mkdtemp(dir=self.home)
        r = path_shortener(path=p, short_paths=short_paths)

        self.assertEqual(self.home_short in r, short_paths)
        self.assertEqual(self.home in r, not short_paths)

    @parameterized.expand([(False,), (True,)])
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

