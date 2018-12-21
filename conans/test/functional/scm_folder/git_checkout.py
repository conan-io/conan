# coding=utf-8

import os
import textwrap

from parameterized import parameterized

from conans.client.tools import environment_append
from conans.test.utils.tools import SVNLocalRepoTestCase
from conans.test.utils.tools import TestClient, create_local_git_repo


class SCMFolderGITCheckout(SVNLocalRepoTestCase):
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

    def setUp(self):
        self.lib1_ref = "lib1/version@user/channel"
        self.lib2_ref = "lib2/version@user/channel"
        self.url, _ = create_local_git_repo(files={'lib1/conanfile.py': self.conanfile,
                                                   'lib1/file.txt': self.lib1_ref})

    def test_local_workflow_root_folder(self):
        t = TestClient(path_with_spaces=False)
        t.runner('git clone "{}" .'.format(self.url), cwd=t.current_folder)
        t.runner("ls -la", cwd=t.current_folder)

        with environment_append({'CONAN_USERNAME': "user", "CONAN_CHANNEL": "channel"}):
            # Local workflow (from root folder)
            t.run("install lib1 -if tmp")
            t.run("source lib1 -if tmp -sf src")
            t.run("build lib1 -if tmp -sf src -bf build")
            self.assertIn(">>>> I'm None/None@user/channel".format(self.lib1_ref), t.out)
            self.assertIn(">>>> content: {}".format(self.lib1_ref), t.out)

    def test_local_workflow_inner_folder(self):
        t = TestClient(path_with_spaces=False)
        t.runner('git clone "{}" .'.format(self.url), cwd=t.current_folder)

        with environment_append({'CONAN_USERNAME': "user", "CONAN_CHANNEL": "channel"}):
            # Local workflow (from inner folder)
            lib1_path = os.path.join(t.current_folder, "lib1")
            old_path = t.current_folder
            try:
                t.current_folder = lib1_path
                t.run("install . -if tmp", )
                t.run("source . -if tmp -sf src")
                t.run("build . -if tmp -sf src -bf build")
                self.assertIn(">>>> I'm None/None@user/channel".format(self.lib1_ref), t.out)
                self.assertIn(">>>> content: {}".format(self.lib1_ref), t.out)
            finally:
                t.current_folder = old_path

    def test_remote_workflow(self):
        t = TestClient(path_with_spaces=False)
        t.runner('git clone "{}" .'.format(self.url), cwd=t.current_folder)

        # Remote workflow
        t.run("create lib1 {}".format(self.lib1_ref))
        self.assertIn(">>>> I'm {}".format(self.lib1_ref), t.out)
        self.assertIn(">>>> content: {}".format(self.lib1_ref), t.out)
