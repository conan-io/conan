# coding=utf-8

import os
import textwrap
import unittest

from nose.plugins.attrib import attr

from conans.test.functional.scm.workflows.common import TestWorkflow
from conans.test.utils.tools import SVNLocalRepoTestCase
from conans.test.utils.tools import TestClient, create_local_git_repo


class ConanfileInRepoRoot(TestWorkflow):
    """ The conanfile.py is in the root of the package """

    path_to_conanfile = "."
    path_from_conanfile_to_root = "."


@attr("svn")
class SVNAutoConanfileInRepoRootTest(ConanfileInRepoRoot, SVNLocalRepoTestCase):
    """ Test SCM url='auto' with SVN, it can only work if conanfile is in the root of the repo """
    conanfile = ConanfileInRepoRoot.conanfile_base.format(extra_header="",
                                                          type="svn",
                                                          url="\"auto\"")

    def setUp(self):
        self.lib1_ref = "lib1/version@user/channel"
        files = self.get_files(subfolder='lib1', conanfile=self.conanfile, lib_ref=self.lib1_ref)
        self.url, _ = self.create_project(files=files)

    # Local workflow
    def test_local_root_folder(self):
        t = TestClient(path_with_spaces=False)
        t.runner("svn co {}/lib1 .".format(self.url), cwd=t.current_folder)
        self._run_local_test(t, t.current_folder, self.path_to_conanfile)

    def test_local_monorepo(self):
        t = TestClient(path_with_spaces=False)
        t.runner("svn co {} .".format(self.url), cwd=t.current_folder)
        self._run_local_test(t, t.current_folder, os.path.join("lib1", self.path_to_conanfile))

    def test_local_monorepo_chdir(self):
        t = TestClient(path_with_spaces=False)
        t.runner("svn co {} .".format(self.url), cwd=t.current_folder)
        self._run_local_test(t, os.path.join(t.current_folder, "lib1"), self.path_to_conanfile)

    # Cache workflow
    def test_remote_root_folder(self):
        t = TestClient(path_with_spaces=False)
        t.runner("svn co {}/lib1 .".format(self.url), cwd=t.current_folder)
        self._run_remote_test(t, t.current_folder, self.path_to_conanfile)
        self.assertIn("Repo origin deduced by 'auto':", t.out)

    def test_remote_monorepo(self):
        t = TestClient(path_with_spaces=False)
        t.runner("svn co {} .".format(self.url), cwd=t.current_folder)
        self._run_remote_test(t, t.current_folder, os.path.join("lib1", self.path_to_conanfile))
        self.assertIn("Repo origin deduced by 'auto':", t.out)

    def test_remote_monorepo_chdir(self):
        t = TestClient(path_with_spaces=False)
        t.runner("svn co {} .".format(self.url), cwd=t.current_folder)
        self._run_remote_test(t, os.path.join(t.current_folder, "lib1"), self.path_to_conanfile)
        self.assertIn("Repo origin deduced by 'auto':", t.out)


@attr("svn")
class SVNConanfileInRepoRootTest(ConanfileInRepoRoot, SVNLocalRepoTestCase):

    extra_header = textwrap.dedent("""\
        def get_remote_url():
            here = os.path.dirname(__file__)
            svn = tools.SVN(os.path.join(here, "%s"))
            return svn.get_remote_url()
        """ % ConanfileInRepoRoot.path_from_conanfile_to_root)

    conanfile = ConanfileInRepoRoot.conanfile_base.format(extra_header=extra_header,
                                                          type="svn",
                                                          url="get_remote_url()")

    def setUp(self):
        self.lib1_ref = "lib1/version@user/channel"
        files = self.get_files(subfolder='lib1', conanfile=self.conanfile, lib_ref=self.lib1_ref)
        self.url, _ = self.create_project(files=files)

    # Local workflow
    def test_local_root_folder(self):
        t = TestClient(path_with_spaces=False)
        t.runner("svn co {}/lib1 .".format(self.url), cwd=t.current_folder)
        self._run_local_test(t, t.current_folder, self.path_to_conanfile)

    def test_local_monorepo(self):
        t = TestClient(path_with_spaces=False)
        t.runner("svn co {} .".format(self.url), cwd=t.current_folder)
        self._run_local_test(t, t.current_folder, os.path.join("lib1", self.path_to_conanfile))

    def test_local_monorepo_chdir(self):
        t = TestClient(path_with_spaces=False)
        t.runner("svn co {} .".format(self.url), cwd=t.current_folder)
        self._run_local_test(t, os.path.join(t.current_folder, "lib1"), self.path_to_conanfile)

    # Cache workflow
    def test_remote_root_folder(self):
        t = TestClient(path_with_spaces=False)
        t.runner("svn co {}/lib1 .".format(self.url), cwd=t.current_folder)
        self._run_remote_test(t, t.current_folder, self.path_to_conanfile)
        self.assertNotIn("Repo origin deduced by 'auto':", t.out)

    def test_remote_monorepo(self):
        t = TestClient(path_with_spaces=False)
        t.runner("svn co {} .".format(self.url), cwd=t.current_folder)
        self._run_remote_test(t, t.current_folder, os.path.join("lib1", self.path_to_conanfile))
        self.assertNotIn("Repo origin deduced by 'auto':", t.out)

    def test_remote_monorepo_chdir(self):
        t = TestClient(path_with_spaces=False)
        t.runner("svn co {} .".format(self.url), cwd=t.current_folder)
        self._run_remote_test(t, os.path.join(t.current_folder, "lib1"), self.path_to_conanfile)
        self.assertNotIn("Repo origin deduced by 'auto':", t.out)


class GitConanfileInRepoRootTest(ConanfileInRepoRoot, unittest.TestCase):

    conanfile = ConanfileInRepoRoot.conanfile_base.format(extra_header="",
                                                          type="git",
                                                          url="\"auto\"")

    def setUp(self):
        self.lib1_ref = "lib1/version@user/channel"
        files = self.get_files(subfolder=".", conanfile=self.conanfile, lib_ref=self.lib1_ref)
        self.url, _ = create_local_git_repo(files=files)

    # Local workflow
    def test_local_root_folder(self):
        t = TestClient(path_with_spaces=False)
        t.runner('git clone "{}" .'.format(self.url), cwd=t.current_folder)
        self._run_local_test(t, t.current_folder, self.path_to_conanfile)

    # Cache workflow
    def test_remote_root_folder(self):
        t = TestClient(path_with_spaces=False)
        t.runner('git clone "{}" .'.format(self.url), cwd=t.current_folder)
        self._run_remote_test(t, t.current_folder, self.path_to_conanfile)
