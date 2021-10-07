# coding=utf-8

import os
import textwrap
import unittest

import pytest

from conans.test.integration.scm.workflows.common import TestWorkflow
from conans.test.utils.scm import create_local_git_repo, SVNLocalRepoTestCase
from conans.test.utils.tools import TestClient


class ConanfileInSubfolder(TestWorkflow):
    """ The conanfile.py is in a subfolder inside the package """

    path_to_conanfile = "conan"
    path_from_conanfile_to_root = ".."


@pytest.mark.tool_svn
class SVNConanfileInSubfolderTest(ConanfileInSubfolder, SVNLocalRepoTestCase):

    extra_header = textwrap.dedent("""\
        def get_remote_url():
            here = os.path.dirname(__file__)
            svn = tools.SVN(os.path.join(here, "%s"))
            return svn.get_remote_url()
        """ % ConanfileInSubfolder.path_from_conanfile_to_root)

    conanfile = ConanfileInSubfolder.conanfile_base.format(extra_header=extra_header,
                                                           type="svn",
                                                           url="get_remote_url()",
                                                           scm_subfolder=ConanfileInSubfolder.scm_subfolder)

    def setUp(self):
        self.lib1_ref = "lib1/version@user/channel"
        files = self.get_files(subfolder='lib1', conanfile=self.conanfile, lib_ref=self.lib1_ref)
        self.url, _ = self.create_project(files=files)

    # Local workflow
    def test_local_root_folder(self):
        t = TestClient(path_with_spaces=False)
        t.run_command("svn co {}/lib1 .".format(self.url))
        self._run_local_test(t, t.current_folder, self.path_to_conanfile)

    def test_local_monorepo(self):
        t = TestClient(path_with_spaces=False)
        t.run_command("svn co {} .".format(self.url))
        self._run_local_test(t, t.current_folder, os.path.join("lib1", self.path_to_conanfile))

    def test_local_monorepo_chdir(self):
        t = TestClient(path_with_spaces=False)
        t.run_command("svn co {} .".format(self.url))
        self._run_local_test(t, os.path.join(t.current_folder, "lib1"), self.path_to_conanfile)

    # Cache workflow
    def test_remote_root_folder(self):
        t = TestClient(path_with_spaces=False)
        t.run_command("svn co {}/lib1 .".format(self.url))
        self._run_remote_test(t, t.current_folder, self.path_to_conanfile)

    def test_remote_monorepo(self):
        t = TestClient(path_with_spaces=False)
        t.run_command("svn co {} .".format(self.url))
        self._run_remote_test(t, t.current_folder, os.path.join("lib1", self.path_to_conanfile))

    def test_remote_monorepo_chdir(self):
        t = TestClient(path_with_spaces=False)
        t.run_command("svn co {} .".format(self.url))
        self._run_remote_test(t, os.path.join(t.current_folder, "lib1"), self.path_to_conanfile)


@pytest.mark.tool_git
class GitConanfileInSubfolderTest(ConanfileInSubfolder, unittest.TestCase):

    conanfile = ConanfileInSubfolder.conanfile_base.format(extra_header="",
                                                           type="git",
                                                           url="\"auto\"",
                                                           scm_subfolder=ConanfileInSubfolder.scm_subfolder)

    def setUp(self):
        self.lib1_ref = "lib1/version@user/channel"
        files = self.get_files(subfolder=".", conanfile=self.conanfile, lib_ref=self.lib1_ref)
        self.url, _ = create_local_git_repo(files=files)

    # Local workflow
    def test_local_root_folder(self):
        t = TestClient(path_with_spaces=False)
        t.run_command('git clone "{}" .'.format(self.url))
        self._run_local_test(t, t.current_folder, self.path_to_conanfile)

    # Cache workflow
    def test_remote_root_folder(self):
        t = TestClient(path_with_spaces=False)
        t.run_command('git clone "{}" .'.format(self.url))
        self._run_remote_test(t, t.current_folder, self.path_to_conanfile)
