import os
import platform
import unittest
from conans.paths import (BUILD_FOLDER, PACKAGES_FOLDER, EXPORT_FOLDER, conan_expand_user,
                          SimplePaths)
from conans.model.ref import ConanFileReference, PackageReference
from conans.test.utils.test_files import temp_folder


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
