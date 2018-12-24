# coding=utf-8

import os
import textwrap
import unittest

from parameterized import parameterized

from conans.client.tools import environment_append
from conans.test.utils.tools import TestClient, create_local_git_repo


class SCMFolderGitTest(unittest.TestCase):
    conanfile = textwrap.dedent("""\
        import os
        from conans import ConanFile, tools

        class Pkg(ConanFile):
            scm = {"type": "git",
                   "url": "auto",
                   "revision": "auto"}

            def build(self):
                content = tools.load(os.path.join(self.source_folder, "file.txt"))
                self.output.info(">>>> I'm {}/{}@{}/{}".format(self.name, self.version, 
                                                               self.user, self.channel))
                self.output.info(">>>> content: {} ".format(content)) 
        """)

    def run(self, *args, **kwargs):
        with environment_append({'CONAN_USERNAME': "user",
                                 'CONAN_CHANNEL': "channel"}):
            super(SCMFolderGitTest, self).run(*args, **kwargs)

    def setUp(self):
        self.lib1_ref = "lib1/version@user/channel"
        self.url, _ = create_local_git_repo(files={'lib1/conanfile.py': self.conanfile,
                                                   'lib1/file.txt': self.lib1_ref})

    def _run_local_test(self, t, working_dir, path_to_conanfile):
        old_wd = t.current_folder
        try:
            t.current_folder = working_dir
            t.run("install {} -if tmp".format(path_to_conanfile))
            t.run("source {} -if tmp -sf src".format(path_to_conanfile))
            t.run("build {} -if tmp -sf src -bf build".format(path_to_conanfile))
            self.assertIn(">>>> I'm None/None@user/channel".format(self.lib1_ref), t.out)
            self.assertIn(">>>> content: {}".format(self.lib1_ref), t.out)
        finally:
            t.current_folder = old_wd

    @parameterized.expand([("True",), ("False",)])
    def test_local_workflow_root_folder(self, use_scm_folder):
        with environment_append({'USE_SCM_FOLDER': use_scm_folder}):
            t = TestClient(path_with_spaces=False)
            t.runner('git clone "{}" .'.format(self.url), cwd=t.current_folder)

            # Local workflow (from root folder)
            self._run_local_test(t, t.current_folder, "lib1")

    @parameterized.expand([("True",), ("False",)])
    def test_local_workflow_inner_folder(self, use_scm_folder):
        with environment_append({'USE_SCM_FOLDER': use_scm_folder}):
            t = TestClient(path_with_spaces=False)
            t.runner('git clone "{}" .'.format(self.url), cwd=t.current_folder)

            # Local workflow (from inner folder)
            self._run_local_test(t, os.path.join(t.current_folder, "lib1"), ".")

    def _run_remote_test(self, t, working_dir, path_to_conanfile):
        old_wd = t.current_folder
        try:
            t.current_folder = working_dir
            t.run("create {} {}".format(path_to_conanfile, self.lib1_ref))
            self.assertIn(">>>> I'm {}".format(self.lib1_ref), t.out)
            self.assertIn(">>>> content: {}".format(self.lib1_ref), t.out)
        finally:
            t.current_folder = old_wd

    @parameterized.expand([("True",), ("False",)])
    def test_remote_workflow(self, use_scm_folder):
        with environment_append({"USE_SCM_FOLDER": use_scm_folder}):
            t = TestClient(path_with_spaces=False)
            t.runner('git clone "{}" .'.format(self.url), cwd=t.current_folder)
            self._run_remote_test(t, t.current_folder, "lib1")

    @parameterized.expand([("True",), ("False",)])
    def test_remote_workflow_chdir(self, use_scm_folder):
        with environment_append({"USE_SCM_FOLDER": use_scm_folder}):
            t = TestClient(path_with_spaces=False)
            t.runner('git clone "{}" .'.format(self.url), cwd=t.current_folder)
            self._run_remote_test(t, os.path.join(t.current_folder, "lib1"), ".")
