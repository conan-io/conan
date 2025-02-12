import os
import platform
import textwrap

import pytest

from conan.api.model import RecipeReference
from conan.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() == "Windows", reason="symlink need admin privileges")
class TestFixSymlinks:
    name_ref = RecipeReference.loads("name/version")

    conanfile = textwrap.dedent("""
        import os
        import shutil
        from conan import ConanFile
        from conan.tools.files import save
        from conan.tools.files.symlinks import (absolute_to_relative_symlinks,
                                                remove_external_symlinks,
                                                remove_broken_symlinks)

        class Recipe(ConanFile):

            def build(self):
                save(self, os.path.join(self.build_folder, "build.txt"), "contents")

            def package(self):
                os.symlink('/dev/null', os.path.join(self.package_folder, "black_hole"))

                # Files: Symlink to file outside the package
                os.symlink(os.path.join(self.build_folder, "build.txt"),
                           os.path.join(self.package_folder, "outside_symlink.txt"))

                # Files: A regular file with symlinks to it
                save(self, os.path.join(self.package_folder, "regular.txt"), "contents")
                os.symlink(os.path.join(self.package_folder, "regular.txt"),
                           os.path.join(self.package_folder, "absolute_symlink.txt"))
                os.symlink("regular.txt", os.path.join(self.package_folder, "relative_symlink.txt"))

                # Files: A broken symlink
                save(self, os.path.join(self.package_folder, "file.txt"), "contents")
                os.symlink(os.path.join(self.package_folder, "file.txt"),
                           os.path.join(self.package_folder, "broken.txt"))
                os.unlink(os.path.join(self.package_folder, "file.txt"))

                # Folder: Symlink outside package
                os.symlink(self.build_folder, os.path.join(self.package_folder, "outside_folder"))

                # Folder: a regular folder and symlinks to it
                save(self, os.path.join(self.package_folder, "folder", "file.txt"), "contents")
                os.symlink(os.path.join(self.package_folder, "folder"),
                           os.path.join(self.package_folder, "absolute"))
                os.symlink("folder", os.path.join(self.package_folder, "relative"))

                # Folder: broken symlink
                save(self, os.path.join(self.package_folder, "tmp", "file.txt"), "contents")
                os.symlink(os.path.join(self.package_folder, "tmp"),
                           os.path.join(self.package_folder, "broken_folder"))
                shutil.rmtree(os.path.join(self.package_folder, "tmp"))

                #
                os.symlink(os.path.join(self.package_folder, "folder", "file.txt"),
                           os.path.join(self.package_folder, "abs_to_file_in_folder.txt"))

                # --> Run the tools
                absolute_to_relative_symlinks(self, self.package_folder)
                remove_external_symlinks(self, self.package_folder)
                remove_broken_symlinks(self, self.package_folder)
    """)

    def test_error_reported(self):
        t = TestClient()
        t.save({'conanfile.py': self.conanfile})
        t.run("create . --name=name --version=version")
        package_folder = t.created_layout().package()

        assert sorted(os.listdir(package_folder)) == ['abs_to_file_in_folder.txt',
                                                      'absolute',
                                                      'absolute_symlink.txt',
                                                      'conaninfo.txt',
                                                      'conanmanifest.txt',
                                                      'folder',
                                                      'regular.txt',
                                                      'relative',
                                                      'relative_symlink.txt']
        # All the links in the package_folder are relative and contained into it
        for (dirpath, dirnames, filenames) in os.walk(package_folder):
            for filename in filenames:
                filename = os.path.join(dirpath, filename)
                if os.path.islink(filename):
                    rel_path = str(os.readlink(filename))
                    assert not os.path.exists(os.path.abspath(rel_path))
                    assert not rel_path.startswith('..')
            for dirname in dirnames:
                dirname = os.path.join(dirpath, dirname)
                if os.path.islink(dirname):
                    rel_path = str(os.readlink(dirname))
                    assert not os.path.exists(os.path.abspath(rel_path))
                    assert not rel_path.startswith('..')
