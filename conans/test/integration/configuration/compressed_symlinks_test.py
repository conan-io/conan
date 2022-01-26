import os
import platform
import unittest

import pytest

from conans.model.recipe_ref import RecipeReference
from conans.paths import PACKAGE_TGZ_NAME
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestServer, TurboTestClient


class CompressSymlinksZeroSize(unittest.TestCase):

    @pytest.mark.skipif(platform.system() != "Linux", reason="Only linux")
    def test_package_symlinks_zero_size(self):
        server = TestServer()
        client = TurboTestClient(servers={"default": server}, inputs=["admin", "password"])

        conanfile = """
import os
from conan import ConanFile, tools

class HelloConan(ConanFile):

    def package(self):
        # Link to file.txt and then remove it
        tools.save(os.path.join(self.package_folder, "file.txt"), "contents")
        os.symlink("file.txt", os.path.join(self.package_folder, "link.txt"))
"""
        ref = RecipeReference.loads("lib/1.0@conan/stable")
        # By default it is not allowed
        pref = client.create(ref, conanfile=conanfile)
        client.create(ref, conanfile=conanfile)
        # Upload, it will create the tgz
        client.upload_all(ref)

        # We can uncompress it without warns
        p_folder = client.get_latest_pkg_layout(pref).download_package()
        tgz = os.path.join(p_folder, PACKAGE_TGZ_NAME)
        client.run_command('gzip -d "{}"'.format(tgz))
        client.run_command('tar tvf "{}"'.format(os.path.join(p_folder, "conan_package.tar")))
        lines = str(client.out).splitlines()
        """
-rw-r--r-- 0/0               8 1970-01-01 01:00 file.txt
lrw-r--r-- 0/0               0 1970-01-01 01:00 link.txt -> file.txt
        """

        self.assertIn("link.txt", " ".join(lines))
        for line in lines:
            if ".txt" not in line:
                continue

            size = int([i for i in line.split(" ") if i][2])
            if "link.txt" in line:
                self.assertEqual(int(size), 0)
            elif "file.txt":
                self.assertGreater(int(size), 0)


@pytest.mark.skipif(platform.system() != "Linux", reason="Only linux")
@pytest.mark.parametrize("package_files",
     [{"files": ["foo/bar/folder/file.txt", "foo/bar/folder/other/other_file.txt"],
       "symlinks": [("../file.txt", "foo/bar/folder/other/file2.txt")]},  # relative ../ symlink
      {"files": ["foo/bar/file/file.txt"],
       "symlinks": [(temp_folder(), "foo/symlink_folder")]},  # absolute symlink
      {"files": ["folder/file.txt"],
       "symlinks": [("folder", "folder2"),
                   ("file.txt", "folder/file2.txt")]},  # single level symlink
      {"files": ["foo/bar/file/file.txt"],
       "symlinks": [("bar/file", "foo/symlink_folder"),
                    ("foo/symlink_folder/file.txt", "file2.txt")]},   # double level symlink
     ])
def test_package_with_symlinks(package_files):

    client = TurboTestClient(default_server_user=True)
    client2 = TurboTestClient(servers=client.servers)
    client.save({"conanfile.py": GenConanfile().with_package('self.copy("*")')
                .with_exports_sources("*")})

    for path in package_files["files"]:
        client.save({path: "foo contents"})

    for link_dst, linked_file in package_files["symlinks"]:
        os.symlink(link_dst, os.path.join(client.current_folder, linked_file))

    pref = client.create(RecipeReference.loads("lib/1.0"), conanfile=False)

    def assert_folder_symlinks(base_folder):
        for link_dst, linked_file in package_files["symlinks"]:
            symlink_package = os.path.join(base_folder, linked_file)
            destination = os.readlink(symlink_package)
            assert destination == link_dst
            assert os.path.exists(symlink_package)
            if os.path.isfile(symlink_package):
                with open(symlink_package) as _f:
                    assert "foo contents" == _f.read()

    # Check exported sources are there
    exports_sources_folder = client.get_latest_ref_layout(pref.ref).export_sources()
    assert_folder_symlinks(exports_sources_folder)

    # Check files have been copied to the build
    build_folder = client.get_latest_pkg_layout(pref).build()
    assert_folder_symlinks(build_folder)

    # Check package files are there
    package_folder = client.get_latest_pkg_layout(pref).package()
    assert_folder_symlinks(package_folder)

    # Zip and upload
    client.run("upload '*' -c -r default")

    # Client 2 install
    client2.run("install --reference lib/1.0@")
    # Check package files are there
    package_folder = client2.get_latest_pkg_layout(pref).package()
    assert_folder_symlinks(package_folder)
