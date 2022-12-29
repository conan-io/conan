import os
import platform
import textwrap
import unittest

import pytest

from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient
from conans.test.utils.tools import TestServer, TurboTestClient


@pytest.mark.skipif(platform.system() == "Windows", reason="Better to test only in NIX the symlinks")
class TestSkipBrokenSymlinks(unittest.TestCase):

    def test_package_broken_symlinks(self):
        server = TestServer()
        client = TurboTestClient(servers={"default": server})
        client2 = TurboTestClient(servers={"default": server})

        conanfile = """
import os
from conans import ConanFile, tools

class HelloConan(ConanFile):

    def package(self):
        # Link to file.txt and then remove it
        tools.save(os.path.join(self.package_folder, "file.txt"), "contents")
        os.symlink(os.path.join(self.package_folder, "file.txt"),
                   os.path.join(self.package_folder, "link.txt"))
        os.unlink(os.path.join(self.package_folder, "file.txt"))

"""
        ref = ConanFileReference.loads("lib/1.0@conan/stable")
        # By default it is not allowed
        client.create(ref, conanfile=conanfile, assert_error=True)
        self.assertIn("The file is a broken symlink", client.out)

        # Until we deactivate the checks
        client.run("config set general.skip_broken_symlinks_check=True")
        pref = client.create(ref, conanfile=conanfile)
        self.assertIn("Created package", client.out)
        p_folder = client.cache.package_layout(pref.ref).package(pref)

        # The link is there
        link_path = os.path.join(p_folder, "link.txt")
        self.assertTrue(os.path.islink(link_path))

        # The link is broken
        target_path = os.readlink(link_path)
        self.assertFalse(os.path.exists(target_path))

        # We can upload the package and reuse it
        client.upload_all(ref)

        client2.run("install {}".format(ref))
        self.assertIn("Downloaded package", client2.out)

    def test_broken_in_local_sources(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile, CMake

            class SymlinksConan(ConanFile):
                name = "symlinks"
                version = "1.0.0"
                exports_sources = "src/*"
            """)

        t = TestClient()
        t.save({'conanfile.py': conanfile, 'src/file': "content"})

        # Create a broken symlink
        broken_symlink = os.path.join(t.current_folder, 'src', 'link')
        os.symlink('not-existing', broken_symlink)

        # Check the bronken symlink locally
        self.assertTrue(os.path.islink(broken_symlink))
        self.assertFalse(os.path.exists(broken_symlink))
        self.assertFalse(os.path.exists(os.path.realpath(broken_symlink)))

        t.run("export . user/channel", assert_error=True)
        self.assertIn("ERROR: The file is a broken symlink", t.out)
