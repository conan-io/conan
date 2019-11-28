import os
import platform
import textwrap
import unittest

from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient
from conans.test.utils.tools import TestServer, TurboTestClient
from conans.client.tools.env import environment_append


@unittest.skipIf(platform.system() == "Windows", "Better to test only in NIX the symlinks")
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

        # Broken link is in the installed package (Conan doesn't filter symlink uncompressing)
        p2_folder = client2.cache.package_layout(pref.ref).package(pref)
        self.assertTrue(os.path.islink(os.path.join(p2_folder, "link.txt")))

    def test_broken_in_local_sources(self):
        ref = ConanFileReference.loads("symlinks/1.0.0@user/channel")
        conanfile = textwrap.dedent("""
            from conans import ConanFile, CMake

            class SymlinksConan(ConanFile):
                name = "symlinks"
                version = "1.0.0"
                exports_sources = "src/*"
                
                def package(self):
                    self.copy("*", src="src", dst="src", symlinks=True)
            """)

        t = TurboTestClient(path_with_spaces=False)
        t.save({'conanfile.py': conanfile, 'src/file': "content"})

        # Create a broken symlink
        broken_symlink = os.path.join(t.current_folder, 'src', 'link.txt')
        os.symlink('not-existing', broken_symlink)

        # Check the broken symlink locally
        self.assertTrue(os.path.islink(broken_symlink))
        self.assertFalse(os.path.exists(broken_symlink))
        self.assertFalse(os.path.exists(os.path.realpath(broken_symlink)))

        t.run("export . user/channel", assert_error=True)
        self.assertIn("ERROR: The file is a broken symlink", t.out)

        # Until we deactivate the checks
        with environment_append({"CONAN_SKIP_BROKEN_SYMLINKS_CHECK": "1"}):
            # t.run("config set general.skip_broken_symlinks_check=True")
            pref = t.create(ref, conanfile=None)
            self.assertIn("Created package", t.out)

        # The broken link should be in sources
        source_folder = t.cache.package_layout(pref.ref).source()
        self.assertTrue(os.path.islink(os.path.join(source_folder, "src", "link.txt")))

        # The broken link should be in build
        build_folder = t.cache.package_layout(pref.ref).build(pref)
        self.assertTrue(os.path.islink(os.path.join(build_folder, "src", "link.txt")))

        # The broken link should be in package
        package_folder = t.cache.package_layout(pref.ref).package(pref)
        self.assertTrue(os.path.islink(os.path.join(package_folder, "src", "link.txt")))
