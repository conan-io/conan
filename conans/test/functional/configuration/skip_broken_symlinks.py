import os
import platform
import textwrap
import unittest

from parameterized.parameterized import parameterized

from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient
from conans.test.utils.tools import TestServer, TurboTestClient, create_local_git_repo
from conans.test.utils.tools import SVNLocalRepoTestCase


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


@unittest.skipIf(platform.system() == "Windows", "Better to test only in NIX the symlinks")
class BrokenLinksSCM(SVNLocalRepoTestCase):
    conanfile = textwrap.dedent("""
        import os
        from conans import ConanFile, tools

        class SymlinkRepo(ConanFile):
            name = "symrepo"
            version = "0.1"
            scm = {{"type": "{}", "revision": "auto", "url": "auto"}}

            def source(self):
                # Linked file
                linked_file = os.path.join(self.source_folder, 'file.txt')
                self.output.info(">> linked-file islink: {{}}".format(os.path.islink(linked_file)))
                self.output.info(">> linked-file exists: {{}}".format(os.path.exists(linked_file)))

                # Linked folder
                linked_folder = os.path.join(self.source_folder, 'folder')
                self.output.info(">> linked-folder islink: {{}}".format(os.path.islink(linked_folder)))
                self.output.info(">> linked-folder exists: {{}}".format(os.path.exists(linked_folder)))
        """)

    def _run_actual_testing(self, t, use_optimization):
        if use_optimization:
            # Just create
            t.run("create . user/channel")
        else:
            # Export and compile
            t.run("export . user/channel")
            t.run("install symrepo/0.1@user/channel --build=symrepo")

        # Link to file
        self.assertIn("symrepo/0.1@user/channel: >> linked-file islink: True", t.out)
        self.assertIn("symrepo/0.1@user/channel: >> linked-file exists: False", t.out)

        # Link to folder
        self.assertIn("symrepo/0.1@user/channel: >> linked-folder islink: False", t.out)
        self.assertIn("symrepo/0.1@user/channel: >> linked-folder exists: False", t.out)

    @parameterized.expand([(False,), (True,)])
    def test_git(self, use_optimization):
        """ The GIT repository contains broken symlinks """
        conanfile = self.conanfile.format("git")

        url, _ = create_local_git_repo(files={'conanfile.py': conanfile})
        t = TestClient()
        t.run_command('git clone "{}" .'.format(url))
        os.symlink('file-not-exists', os.path.join(t.current_folder, 'file.txt'))
        os.symlink('folder-not-exists', os.path.join(t.current_folder, 'folder'))
        t.run_command('git add file.txt')
        t.run_command('git add folder/file.txt')  # It won't add linked folders

        t.run_command('git commit -m "add link to externals"')
        t.run_command('git push')

        self._run_actual_testing(t, use_optimization)

    @parameterized.expand([(False,), (True,)])
    def test_svn(self, use_optimization):
        """ The SVN repository contains broken symlinks """
        conanfile = self.conanfile.format("svn")

        url, _ = self.create_project(files={'conanfile.py': conanfile})
        t = TestClient()
        t.run_command('svn co "{}" .'.format(url))

        os.symlink('file-not-exists', os.path.join(t.current_folder, 'file.txt'))
        os.symlink('folder-not-exists', os.path.join(t.current_folder, 'folder'))
        t.run_command('svn add file.txt')
        t.run_command('svn add folder')
        t.run_command('svn add folder/file.txt')  # It won't add linked files in folders

        t.run_command('svn commit -m "add link to externals"')
        t.run_command('svn update')

        self._run_actual_testing(t, use_optimization)

