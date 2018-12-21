# coding=utf-8

import os
import textwrap

from parameterized import parameterized

from conans.client.tools import environment_append
from conans.test.utils.tools import SVNLocalRepoTestCase
from conans.test.utils.tools import TestClient


class SCMFolderSVNCheckout(SVNLocalRepoTestCase):
    conanfile = textwrap.dedent("""\
        import os
        from conans import ConanFile, tools

        class Pkg(ConanFile):
            scm = {"type": "svn",
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
        self.url, rev = self.create_project(files={'lib1/conanfile.py': self.conanfile,
                                                   'lib1/file.txt': self.lib1_ref})

    @parameterized.expand([(True, ), (False, )])
    def test_local_workflow_root_folder(self, use_monorepo):
        url_suffix = "" if use_monorepo else "/lib1"
        path_to_lib = "lib1" if use_monorepo else "."

        t = TestClient(path_with_spaces=False)
        t.runner("svn co {}{} .".format(self.url, url_suffix), cwd=t.current_folder)

        with environment_append({'CONAN_USERNAME': "user", "CONAN_CHANNEL": "channel"}):
            # Local workflow (from root folder)
            t.run("install {} -if tmp".format(path_to_lib))
            t.run("source {} -if tmp -sf src".format(path_to_lib))
            t.run("build {} -if tmp -sf src -bf build".format(path_to_lib))
            self.assertIn(">>>> I'm None/None@user/channel".format(self.lib1_ref), t.out)
            self.assertIn(">>>> content: {}".format(self.lib1_ref), t.out)


    @parameterized.expand([(True,), (False,)])
    def test_local_workflow_inner_folder(self, use_monorepo):
        url_suffix = "" if use_monorepo else "/lib1"
        path_to_lib = "lib1" if use_monorepo else "."

        t = TestClient(path_with_spaces=False)
        t.runner("svn co {}{} .".format(self.url, url_suffix), cwd=t.current_folder)

        with environment_append({'CONAN_USERNAME': "user", "CONAN_CHANNEL": "channel"}):
            # Local workflow (from inner folder)
            lib1_path = os.path.join(t.current_folder, path_to_lib)
            try:
                old_path = t.current_folder
                t.current_folder = lib1_path
                t.run("install . -if tmp", )
                t.run("source . -if tmp -sf src")
                t.run("build . -if tmp -sf src -bf build")
                self.assertIn(">>>> I'm None/None@user/channel".format(self.lib1_ref), t.out)
                self.assertIn(">>>> content: {}".format(self.lib1_ref), t.out)
            finally:
                t.current_folder = old_path

    @parameterized.expand([(True,), (False,)])
    def test_remote_workflow(self, use_monorepo):
        url_suffix = "" if use_monorepo else "/lib1"
        path_to_lib = "lib1" if use_monorepo else "."

        t = TestClient(path_with_spaces=False)
        t.runner("svn co {}{} .".format(self.url, url_suffix), cwd=t.current_folder)

        # Remote workflow
        t.run("create {} {}".format(path_to_lib, self.lib1_ref))
        self.assertIn(">>>> I'm {}".format(self.lib1_ref), t.out)
        self.assertIn(">>>> content: {}".format(self.lib1_ref), t.out)
