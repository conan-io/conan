# coding=utf-8
import os
import six
import unittest

from nose.plugins.attrib import attr

from conans.client import tools
from conans.client.tools.scm import Git
from conans.errors import ConanException
from conans.test.utils.tools import temp_folder, create_local_git_repo,\
    TestClient
from conans.util.files import save


class GitRemoteUrlTest(unittest.TestCase):

    def test_remove_credentials(self):
        """ Check that the 'remove_credentials' argument is taken into account """
        expected_url = 'https://myrepo.com/path/to/repo.git'
        origin_url = 'https://username:password@myrepo.com/path/to/repo.git'

        git = Git(folder=temp_folder())
        git.run("init .")
        git.run("remote add origin {}".format(origin_url))

        self.assertEqual(git.get_remote_url(), origin_url)
        self.assertEqual(git.get_remote_url(remove_credentials=True), expected_url)


@attr('git')
class GitToolTest(unittest.TestCase):

    def test_repo_root(self):
        root_path, _ = create_local_git_repo({"myfile": "anything"})

        # Initialized in the root folder
        git = Git(root_path)
        self.assertEqual(root_path, git.get_repo_root())

        # Initialized elsewhere
        subfolder = os.path.join(root_path, 'subfolder')
        os.makedirs(subfolder)
        git = Git(subfolder)
        self.assertEqual(root_path, git.get_repo_root())

    def test_is_pristine(self):
        root_path, _ = create_local_git_repo({"myfile": "anything"})

        git = Git(root_path)
        self.assertTrue(git.is_pristine())

        save(os.path.join(root_path, "other_file"), "content")
        self.assertFalse(git.is_pristine())

        git.run("add .")
        self.assertFalse(git.is_pristine())

        git.run('commit -m "commit"')
        self.assertTrue(git.is_pristine())

    def test_is_local_repository(self):
        root_path, _ = create_local_git_repo({"myfile": "anything"})

        git = Git(temp_folder())
        git.clone(root_path)
        self.assertTrue(git.is_local_repository())
        # TODO: Check that with remote one it is working too

    def test_clone_git(self):
        path, _ = create_local_git_repo({"myfile": "contents"})
        tmp = temp_folder()
        git = Git(tmp)
        git.clone(path)
        self.assertTrue(os.path.exists(os.path.join(tmp, "myfile")))

    def test_clone_existing_folder_git(self):
        path, commit = create_local_git_repo({"myfile": "contents"}, branch="my_release")

        tmp = temp_folder()
        save(os.path.join(tmp, "file"), "dummy contents")
        git = Git(tmp)
        git.clone(path, branch="my_release")
        self.assertTrue(os.path.exists(os.path.join(tmp, "myfile")))

        # Checkout a commit
        git.checkout(commit)
        self.assertEqual(git.get_revision(), commit)

    def test_clone_existing_folder_without_branch(self):
        tmp = temp_folder()
        save(os.path.join(tmp, "file"), "dummy contents")
        git = Git(tmp)
        with six.assertRaisesRegex(self, ConanException, "specify a branch to checkout"):
            git.clone("https://github.com/conan-community/conan-zlib.git")

    def test_credentials(self):
        tmp = temp_folder()
        git = Git(tmp, username="peter", password="otool")
        url_credentials = git.get_url_with_credentials("https://some.url.com")
        self.assertEqual(url_credentials, "https://peter:otool@some.url.com")

    def test_verify_ssl(self):
        class MyRunner(object):
            def __init__(self):
                self.calls = []

            def __call__(self, *args, **kwargs):
                self.calls.append(args[0])
                return ""

        runner = MyRunner()
        tmp = temp_folder()
        git = Git(tmp, username="peter", password="otool", verify_ssl=True, runner=runner,
                  force_english=True)
        git.clone(url="https://myrepo.git")
        self.assertIn("git config http.sslVerify true", runner.calls[1])

        runner = MyRunner()
        git = Git(tmp, username="peter", password="otool", verify_ssl=False, runner=runner,
                  force_english=False)
        git.clone(url="https://myrepo.git")
        self.assertIn("git config http.sslVerify false", runner.calls[1])

    def test_clone_submodule_git(self):
        subsubmodule, _ = create_local_git_repo({"subsubmodule": "contents"})
        submodule, _ = create_local_git_repo({"submodule": "contents"}, submodules=[subsubmodule])
        path, commit = create_local_git_repo({"myfile": "contents"}, submodules=[submodule])

        def _create_paths():
            tmp = temp_folder()
            submodule_path = os.path.join(
                tmp,
                os.path.basename(os.path.normpath(submodule)))
            subsubmodule_path = os.path.join(
                submodule_path,
                os.path.basename(os.path.normpath(subsubmodule)))
            return tmp, submodule_path, subsubmodule_path

        # Check old (default) behaviour
        tmp, submodule_path, _ = _create_paths()
        git = Git(tmp)
        git.clone(path)
        self.assertTrue(os.path.exists(os.path.join(tmp, "myfile")))
        self.assertFalse(os.path.exists(os.path.join(submodule_path, "submodule")))

        # Check invalid value
        tmp, submodule_path, _ = _create_paths()
        git = Git(tmp)
        git.clone(path)
        with six.assertRaisesRegex(self, ConanException,
                                   "Invalid 'submodule' attribute value in the 'scm'."):
            git.checkout(commit, submodule="invalid")

        # Check shallow
        tmp, submodule_path, subsubmodule_path = _create_paths()
        git = Git(tmp)
        git.clone(path)
        git.checkout(commit, submodule="shallow")
        self.assertTrue(os.path.exists(os.path.join(tmp, "myfile")))
        self.assertTrue(os.path.exists(os.path.join(submodule_path, "submodule")))
        self.assertFalse(os.path.exists(os.path.join(subsubmodule_path, "subsubmodule")))

        # Check recursive
        tmp, submodule_path, subsubmodule_path = _create_paths()
        git = Git(tmp)
        git.clone(path)
        git.checkout(commit, submodule="recursive")
        self.assertTrue(os.path.exists(os.path.join(tmp, "myfile")))
        self.assertTrue(os.path.exists(os.path.join(submodule_path, "submodule")))
        self.assertTrue(os.path.exists(os.path.join(subsubmodule_path, "subsubmodule")))

    def git_to_capture_branch_test(self):
        conanfile = """
import re
from conans import ConanFile, tools

def get_version():
    git = tools.Git()
    try:
        branch = git.get_branch()
        branch = re.sub('[^0-9a-zA-Z]+', '_', branch)
        return "%s_%s" % (branch, git.get_revision())
    except:
        return None

class HelloConan(ConanFile):
    name = "Hello"
    version = get_version()

    def build(self):
        assert("r3le_ase__" in self.version)
        assert(len(self.version) == 50)
"""
        path, _ = create_local_git_repo({"conanfile.py": conanfile}, branch="r3le-ase-")
        client = TestClient()
        client.current_folder = path
        client.run("create . user/channel")

    def git_helper_in_recipe_test(self):
        client = TestClient()
        git_repo = temp_folder()
        save(os.path.join(git_repo, "file.h"), "contents")
        client.runner("git init .", cwd=git_repo)
        client.runner('git config user.email "you@example.com"', cwd=git_repo)
        client.runner('git config user.name "Your Name"', cwd=git_repo)
        client.runner("git checkout -b dev", cwd=git_repo)
        client.runner("git add .", cwd=git_repo)
        client.runner('git commit -m "comm"', cwd=git_repo)

        conanfile = """
import os
from conans import ConanFile, tools

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"
    exports_sources = "other"

    def source(self):
        git = tools.Git()
        git.clone("%s", "dev")

    def build(self):
        assert(os.path.exists("file.h"))
""" % git_repo.replace("\\", "/")
        client.save({"conanfile.py": conanfile, "other": "hello"})
        client.run("create . user/channel")

        # Now clone in a subfolder with later checkout
        conanfile = """
import os
from conans import ConanFile, tools

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"
    exports_sources = "other"

    def source(self):
        tools.mkdir("src")
        git = tools.Git("./src")
        git.clone("%s")
        git.checkout("dev")

    def build(self):
        assert(os.path.exists(os.path.join("src", "file.h")))
""" % git_repo.replace("\\", "/")
        client.save({"conanfile.py": conanfile, "other": "hello"})
        client.run("create . user/channel")

        # Base dir, with exports without subfolder and not specifying checkout fails
        conanfile = """
import os
from conans import ConanFile, tools

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"
    exports_sources = "other"

    def source(self):
        git = tools.Git()
        git.clone("%s")

    def build(self):
        assert(os.path.exists("file.h"))
""" % git_repo.replace("\\", "/")
        client.save({"conanfile.py": conanfile, "other": "hello"})
        client.run("create . user/channel", assert_error=True)
        self.assertIn("specify a branch to checkout", client.out)

    def git_commit_message_test(self):
        client = TestClient()
        git_repo = temp_folder()
        client.runner("git init .", cwd=git_repo)
        client.runner('git config user.email "you@example.com"', cwd=git_repo)
        client.runner('git config user.name "Your Name"', cwd=git_repo)
        client.runner("git checkout -b dev", cwd=git_repo)
        git = Git(git_repo)
        self.assertIsNone(git.get_commit_message())
        save(os.path.join(git_repo, "test"), "contents")
        client.runner("git add test", cwd=git_repo)
        client.runner('git commit -m "first commit"', cwd=git_repo)
        self.assertEqual("dev", git.get_branch())
        self.assertEqual("first commit", git.get_commit_message())


class GitToolsTests(unittest.TestCase):

    def setUp(self):
        self.folder, self.rev = create_local_git_repo({'myfile.txt': "contents"})

    def test_no_tag(self):
        """
        No tags has been created in repo
        """
        git = Git(folder=self.folder)
        tag = git.get_tag()
        self.assertIsNone(tag)

    def test_in_tag(self):
        """
        Current checkout is on a tag
        """
        git = Git(folder=self.folder)
        git.run("tag 0.0.0")
        tag = git.get_tag()
        self.assertEqual("0.0.0", tag)

    def test_in_branch_with_tag(self):
        """
        Tag is defined but current commit is ahead of it
        """
        git = Git(folder=self.folder)
        git.run("tag 0.0.0")
        save(os.path.join(self.folder, "file.txt"), "")
        git.run("add .")
        git.run("commit -m \"new file\"")
        tag = git.get_tag()
        self.assertIsNone(tag)

    def test_get_tag_no_git_repo(self):
        """
        Try to get tag out of a git repo
        """
        git = Git(folder=temp_folder())
        with six.assertRaisesRegex(self, ConanException, "Not a valid 'git' repository"):
            git.get_tag()

    def test_excluded_files(self):
        folder = temp_folder()
        save(os.path.join(folder, "file"), "some contents")
        git = Git(folder)
        with tools.environment_append({"PATH": ""}):
            git.excluded_files()
