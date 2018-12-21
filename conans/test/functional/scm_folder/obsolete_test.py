# coding=utf-8

import textwrap
import unittest

from conans.test.utils.tools import TestClient, create_local_git_repo


class SCMFolderObsoleteTest(unittest.TestCase):
    conanfile = textwrap.dedent("""\
        from conans import ConanFile, tools
        
        class Pkg(ConanFile):
            scm = {"type": "git",
                   "url": "auto",
                   "revision": "auto"}

            def build(self):
                content = tools.load("file.txt")
                self.output.info(">>>> I'm {}/{}@{}/{}".format(self.name, self.version, 
                                                               self.user, self.channel))
                self.output.info(">>>> content: {} ".format(content)) 
        """)

    def test_obsolete(self):
        reference = "pkg/v1@user/channel"
        t = TestClient(path_with_spaces=False)

        # Create pkg/v1
        create_local_git_repo(files={'conanfile.py': self.conanfile,
                                     'file.txt': reference},
                              folder=t.current_folder)
        t.runner('git remote add origin https://myrepo.com.git', cwd=t.current_folder)
        t.run("create . {}".format(reference))
        self.assertIn(">>>> I'm {}".format(reference), t.out)
        self.assertIn(">>>> content: {}".format(reference), t.out)

        # Work on pkg to improve it ==> create pkg/v2
        ref_v2 = "pkg/v2@user/channel"
        t.save(files={'conanfile.py': self.conanfile,
                      'file.txt': ref_v2})
        t.runner('git commit -m "up to v2"', cwd=t.current_folder)
        t.run("create . {}".format(ref_v2))
        self.assertIn(">>>> I'm {}".format(ref_v2), t.out)
        self.assertIn(">>>> content: {}".format(ref_v2), t.out)

        # Now, a consumer wants the pkg/v1 and builds it...
        t.run("install {} --build".format(reference))
        self.assertIn(">>>> I'm {}".format(reference), t.out)
        self.assertIn(">>>> content: {}".format(reference), t.out)
