# coding=utf-8

import os
import textwrap
import unittest

from conans.client.tools import environment_append
from conans.test.utils.tools import SVNLocalRepoTestCase
from conans.test.utils.tools import TestClient, create_local_git_repo


class TestWorkflows:
    path_to_conanfile = "."  # TODO: Test with 'conan'
    path_from_conanfile_to_root = "."

    def run(self, *args, **kwargs):
        # path_to_conanfile and path_from_conanfile_to_root must be opposite ones.
        self.assertEqual(os.path.normpath(os.path.join(self.path_to_conanfile,
                                                       self.path_from_conanfile_to_root)),
                         '.')

        with environment_append({'CONAN_USERNAME': "user",
                                 "CONAN_CHANNEL": "channel"}):
            super(TestWorkflows, self).run(*args, **kwargs)

    def create_project(self, files):
        return super(TestWorkflows, self).create_project(files=files)

    def setUp(self):
        self.lib1_ref = "lib1/version@user/channel"
        self.lib2_ref = "lib2/version@user/channel"
        conanfile_path = os.path.join('lib1', self.path_to_conanfile, 'conanfile.py')
        self.url, _ = self.create_project(files={conanfile_path: self.conanfile,
                                                 'lib1/file.txt': self.lib1_ref})

    def _run_local_test(self, t, working_dir, path_to_conanfile):
        old_wd = t.current_folder
        try:
            t.current_folder = working_dir
            t.run("install {} -if tmp".format(path_to_conanfile))
            t.run("source {} -if tmp -sf src".format(path_to_conanfile))
            #t.run("build {} -if tmp -sf src -bf build".format(path_to_conanfile))
            self.assertIn(">>>> I'm None/None@user/channel".format(self.lib1_ref), t.out)
            self.assertIn(">>>> content: {}".format(self.lib1_ref), t.out)
        finally:
            t.current_folder = old_wd

    def _run_remote_test(self, t, working_dir, path_to_conanfile):
        old_wd = t.current_folder
        try:
            t.current_folder = working_dir
            t.run("create {} {}".format(path_to_conanfile, self.lib1_ref))
            self.assertIn(">>>> I'm {}".format(self.lib1_ref), t.out)
            self.assertIn(">>>> content: {}".format(self.lib1_ref), t.out)
        finally:
            t.current_folder = old_wd


class SVNWorkflowsTest(TestWorkflows, unittest.TestCase):

    conanfile = textwrap.dedent("""\
        import os
        from conans import ConanFile, tools

        def get_remote_url():
            here = os.path.dirname(__file__)
            svn = tools.SVN(os.path.join(here, "%s"))
            return svn.get_remote_url()

        class Pkg(ConanFile):
            scm = {"type": "svn",
                   "url": get_remote_url(),
                   "revision": "auto"}

            def source(self):
                self.output.info(self.source_folder)
                content = tools.load(os.path.join(self.source_folder, "file.txt"))
                self.output.info(">>>> I'm {}/{}@{}/{}".format(self.name, self.version, 
                                                               self.user, self.channel))
                self.output.info(">>>> content: {} ".format(content)) 
        """ % TestWorkflows.path_from_conanfile_to_root)

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

    def test_remote_monorepo(self):
        t = TestClient(path_with_spaces=False)
        t.runner("svn co {} .".format(self.url), cwd=t.current_folder)
        self._run_remote_test(t, t.current_folder, os.path.join("lib1", self.path_to_conanfile))

    def test_remote_monorepo_chdir(self):
        t = TestClient(path_with_spaces=False)
        t.runner("svn co {} .".format(self.url), cwd=t.current_folder)
        self._run_remote_test(t, os.path.join(t.current_folder, "lib1"), self.path_to_conanfile)


class GitWorkflowsTest(TestWorkflows, SVNLocalRepoTestCase):

    conanfile = textwrap.dedent("""\
        import os
        from conans import ConanFile, tools

        class Pkg(ConanFile):
            scm = {"type": "git",
                   "url": "auto",
                   "revision": "auto"}

            def source(self):
                self.output.info(self.source_folder)
                content = tools.load(os.path.join(self.source_folder, "file.txt"))
                self.output.info(">>>> I'm {}/{}@{}/{}".format(self.name, self.version, 
                                                               self.user, self.channel))
                self.output.info(">>>> content: {} ".format(content)) 
        """)

    def create_project(self, files):
        return create_local_git_repo(files=files)

    # Local workflow
    def test_local_root_folder(self):
        t = TestClient(path_with_spaces=False)
        t.runner('git clone "{}" .'.format(self.url), cwd=t.current_folder)
        self._run_local_test(t, t.current_folder, os.path.join('lib1', self.path_to_conanfile))

    def test_local_chdir(self):
        t = TestClient(path_with_spaces=False)
        t.runner('git clone "{}" .'.format(self.url), cwd=t.current_folder)
        self._run_local_test(t, os.path.join(t.current_folder, "lib1"), self.path_to_conanfile)

    # Cache workflow
    def test_remote_root_folder(self):
        t = TestClient(path_with_spaces=False)
        t.runner('git clone "{}" .'.format(self.url), cwd=t.current_folder)
        self._run_remote_test(t, t.current_folder, os.path.join('lib1', self.path_to_conanfile))

    def test_remote_monorepo_chdir(self):
        t = TestClient(path_with_spaces=False)
        t.runner('git clone "{}" .'.format(self.url), cwd=t.current_folder)
        self._run_remote_test(t, os.path.join(t.current_folder, "lib1"), self.path_to_conanfile)



