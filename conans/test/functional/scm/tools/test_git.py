# coding=utf-8
import os
import re
import subprocess
import unittest

import pytest
import six
from mock import patch
from parameterized import parameterized

from conans.client import tools
from conans.client.tools.scm import Git
from conans.errors import ConanException
from conans.test.utils.scm import create_local_git_repo
from conans.test.utils.tools import temp_folder, TestClient
from conans.util.files import save


@pytest.mark.tool_git
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


@pytest.mark.tool_git
class GitToolTest(unittest.TestCase):

    @patch('subprocess.Popen')
    def test_version(self, mocked_open):
        mocked_open.return_value.communicate.return_value = ('git version 2.21.0'.encode(), None)
        version = Git.get_version()
        self.assertEqual(version, "2.21.0")

    @patch('subprocess.Popen')
    def test_version_invalid(self, mocked_open):
        mocked_open.return_value.communicate.return_value = ('failed'.encode(), None)
        with self.assertRaises(ConanException):
            Git.get_version()

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

    @parameterized.expand([(None,),  # default
                           ("develop",),  # branch name
                           ("1.0",),  # tag name
                           ("HEAD",),  # expression
                           ])
    def test_clone_git_shallow(self, element):
        path, revision = create_local_git_repo({"myfile": "contents"}, commits=3, tags=["1.0"], branch="develop")
        tmp = temp_folder()
        git = Git(tmp)
        git.clone("file://" + path, branch=element, shallow=True)  # --depth is ignored in local clones
        with self.assertRaises(subprocess.CalledProcessError):
            git.checkout(element="HEAD~1")
        self.assertTrue(os.path.exists(os.path.join(tmp, "myfile")))
        self.assertEqual(git.get_revision(), revision)
        self.assertEqual(git.run("rev-list --all --count"), "1")

    def test_clone_git_shallow_revision(self):
        path, revision = create_local_git_repo({"myfile": "contents"}, commits=3, tags=["1.0"], branch="develop")
        tmp = temp_folder()
        git = Git(tmp)
        if Git.get_version() < "2.13":
            # older Git versions have known bugs with "git fetch origin <sha>":
            # https://github.com/git/git/blob/master/Documentation/RelNotes/2.13.0.txt
            #  * "git fetch" that requests a commit by object name, when the other
            #    side does not allow such an request, failed without much
            #    explanation.
            # https://github.com/git/git/blob/master/Documentation/RelNotes/2.14.0.txt
            # * There is no good reason why "git fetch $there $sha1" should fail
            #    when the $sha1 names an object at the tip of an advertised ref,
            #    even when the other side hasn't enabled allowTipSHA1InWant.
            with self.assertRaises(subprocess.CalledProcessError):
                git.clone("file://" + path, branch=revision, shallow=True)
        else:
            git.clone("file://" + path, branch=revision, shallow=True)
            with self.assertRaises(subprocess.CalledProcessError):
                git.checkout(element="HEAD~1")
            self.assertTrue(os.path.exists(os.path.join(tmp, "myfile")))
            self.assertEqual(git.get_revision(), revision)
            self.assertEqual(git.run("rev-list --all --count"), "1")

    def test_clone_git_shallow_with_local(self):
        path, revision = create_local_git_repo({"repofile": "contents"}, commits=3)
        tmp = temp_folder()
        save(os.path.join(tmp, "localfile"), "contents")
        save(os.path.join(tmp, "indexfile"), "contents")
        git = Git(tmp)
        git.run("init")
        git.run("add indexfile")
        git.clone("file://" + path, branch="master", shallow=True)  # --depth is ignored in local clones
        self.assertTrue(os.path.exists(os.path.join(tmp, "repofile")))
        self.assertTrue(os.path.exists(os.path.join(tmp, "localfile")))
        self.assertTrue(os.path.exists(os.path.join(tmp, "indexfile")))
        self.assertEqual(git.get_revision(), revision)
        self.assertEqual(git.run("rev-list --all --count"), "1")

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
            git.clone("https://github.com/conan-io/hooks.git")

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
        self.assertIn("git -c http.sslVerify=true", runner.calls[0])

        runner = MyRunner()
        git = Git(tmp, username="peter", password="otool", verify_ssl=False, runner=runner,
                  force_english=False)
        git.clone(url="https://myrepo.git")
        self.assertIn("git -c http.sslVerify=false", runner.calls[0])

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

    def test_git_to_capture_branch(self):
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

    def test_git_helper_in_recipe(self):
        client = TestClient()
        git_repo = temp_folder()
        save(os.path.join(git_repo, "file.h"), "contents")
        with client.chdir(git_repo):
            client.run_command("git init .")
            client.run_command('git config user.email "you@example.com"')
            client.run_command('git config user.name "Your Name"')
            client.run_command("git checkout -b dev")
            client.run_command("git add .")
            client.run_command('git commit -m "comm"')

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

    def test_git_commit_message(self):
        client = TestClient()
        git_repo = temp_folder()
        with client.chdir(git_repo):
            client.run_command("git init .")
            client.run_command('git config user.email "you@example.com"')
            client.run_command('git config user.name "Your Name"')
            client.run_command("git checkout -b dev")
        git = Git(git_repo)
        self.assertIsNone(git.get_commit_message())
        save(os.path.join(git_repo, "test"), "contents")
        with client.chdir(git_repo):
            client.run_command("git add test")
            client.run_command('git commit -m "first commit"')
        self.assertEqual("dev", git.get_branch())
        self.assertEqual("first commit", git.get_commit_message())


@pytest.mark.tool_git
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
        # Try to get tag out of a git repo
        tmp_folder = temp_folder()
        git = Git(folder=tmp_folder)
        pattern = "'{0}' is not a valid 'git' repository or 'git' not found".format(
            re.escape(tmp_folder))
        with six.assertRaisesRegex(self, ConanException, pattern):
            git.get_tag()

    def test_excluded_files(self):
        folder = temp_folder()
        save(os.path.join(folder, "file"), "some contents")
        git = Git(folder)
        with tools.environment_append({"PATH": ""}):
            excluded = git.excluded_files()
            self.assertEqual(excluded, [])
