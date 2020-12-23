import os
import platform
import textwrap
import unittest

import pytest

from conans.model.ref import ConanFileReference, PackageReference
from conans.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() == "Windows", reason="symlink need admin privileges")
class FixSymlinksTestCase(unittest.TestCase):
    name_ref = ConanFileReference.loads("name/version")

    conanfile = textwrap.dedent("""
        import os
        import shutil
        from conans import ConanFile, tools

        class Recipe(ConanFile):
            options = {"raise_if_error": [True, False]}
            default_options = {"raise_if_error": False}

            def build(self):
                tools.save(os.path.join(self.build_folder, "build.txt"), "contents")

            def package(self):
                os.symlink('/dev/null', os.path.join(self.package_folder, "black_hole"))

                # Files: Symlink to file outside the package
                os.symlink(os.path.join(self.build_folder, "build.txt"),
                           os.path.join(self.package_folder, "outside_symlink.txt"))

                # Files: A regular file with symlinks to it
                tools.save(os.path.join(self.package_folder, "regular.txt"), "contents")
                os.symlink(os.path.join(self.package_folder, "regular.txt"),
                           os.path.join(self.package_folder, "absolute_symlink.txt"))
                os.symlink("regular.txt", os.path.join(self.package_folder, "relative_symlink.txt"))

                # Files: A broken symlink
                tools.save(os.path.join(self.package_folder, "file.txt"), "contents")
                os.symlink(os.path.join(self.package_folder, "file.txt"),
                           os.path.join(self.package_folder, "broken.txt"))
                os.unlink(os.path.join(self.package_folder, "file.txt"))

                # Folder: Symlink outside package
                os.symlink(self.build_folder, os.path.join(self.package_folder, "outside_folder"))

                # Folder: a regular folder and symlinks to it
                tools.save(os.path.join(self.package_folder, "folder", "file.txt"), "contents")
                os.symlink(os.path.join(self.package_folder, "folder"),
                           os.path.join(self.package_folder, "absolute"))
                os.symlink("folder", os.path.join(self.package_folder, "relative"))

                # Folder: broken symlink
                tools.save(os.path.join(self.package_folder, "tmp", "file.txt"), "contents")
                os.symlink(os.path.join(self.package_folder, "tmp"),
                           os.path.join(self.package_folder, "broken_folder"))
                shutil.rmtree(os.path.join(self.package_folder, "tmp"))

                #
                os.symlink(os.path.join(self.package_folder, "folder", "file.txt"),
                           os.path.join(self.package_folder, "abs_to_file_in_folder.txt"))

                # --> Run the tool
                tools.fix_symlinks(self, raise_if_error=self.options.raise_if_error)
    """)

    def test_error_reported(self):
        t = TestClient()
        t.save({'conanfile.py': self.conanfile})
        t.run("create . {}@ -o raise_if_error=False".format(self.name_ref))
        self.assertIn("name/version: ERROR: file 'outside_symlink.txt' links to a file outside"
                      " the package, it's been removed.", t.out)
        self.assertIn("name/version: ERROR: file 'broken.txt' links to a path that doesn't exist,"
                      " it's been removed.", t.out)
        self.assertIn("name/version: ERROR: file 'broken_folder' links to a path that doesn't"
                      " exist, it's been removed.", t.out)
        self.assertIn("name/version: ERROR: directory 'outside_folder' links to a directory outside"
                      " the package, it's been removed.", t.out)

        # Check the work is done
        pkg_ref = PackageReference(self.name_ref, "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        package_folder = t.cache.package_layout(self.name_ref).package(pkg_ref)

        self.assertListEqual(sorted(os.listdir(package_folder)),
                             ['abs_to_file_in_folder.txt',
                              'absolute',
                              'absolute_symlink.txt',
                              'black_hole',
                              'conaninfo.txt',
                              'conanmanifest.txt',
                              'folder',
                              'regular.txt',
                              'relative',
                              'relative_symlink.txt'])
        # All the links in the package_folder are relative and contained into it
        for (dirpath, dirnames, filenames) in os.walk(package_folder):
            for filename in filenames:
                if os.path.islink(filename):
                    rel_path = os.readlink(filename)
                    self.assertFalse(os.path.abspath(rel_path))
                    self.assertFalse(rel_path.startswith('..'))
            for dirname in dirnames:
                if os.path.islink(dirname):
                    rel_path = os.readlink(dirname)
                    self.assertFalse(os.path.abspath(rel_path))
                    self.assertFalse(rel_path.startswith('..'))

    def test_error_raise(self):
        t = TestClient()
        t.save({'conanfile.py': self.conanfile})
        t.run("create . name/version@ -o raise_if_error=True", assert_error=True)
        self.assertIn("name/version: ERROR: file 'outside_symlink.txt' links to a file outside"
                      " the package, it's been removed.", t.out)
        self.assertIn("name/version: ERROR: file 'broken.txt' links to a path that doesn't exist,"
                      " it's been removed.", t.out)
        self.assertIn("name/version: ERROR: file 'broken_folder' links to a path that doesn't"
                      " exist, it's been removed.", t.out)
        self.assertIn("name/version: ERROR: directory 'outside_folder' links to a directory outside"
                      " the package, it's been removed.", t.out)
        self.assertIn("ConanException: There are invalid symlinks in the package!", t.out)
