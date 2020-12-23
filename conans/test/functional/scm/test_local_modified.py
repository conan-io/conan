# coding=utf-8

import textwrap
import unittest

import pytest

from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient
from conans.test.utils.scm import create_local_git_repo


@pytest.mark.tool_git
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

    def setUp(self):
        self.reference = "pkg/v1@user/channel"
        self.t = TestClient(path_with_spaces=False)

        # Create pkg/v1
        url, _ = create_local_git_repo(files={'conanfile.py': self.conanfile,
                                              'file.txt': self.reference},
                                       folder=self.t.current_folder)
        self.t.run_command('git remote add origin {}'.format(url))
        self.t.run("create . {}".format(self.reference))
        self.assertIn(">>>> I'm {}".format(self.reference), self.t.out)
        self.assertIn(">>>> content: {}".format(self.reference), self.t.out)

        # Change something in the local folder
        self.new_content = "Updated in the local folder!"
        self.t.save({'file.txt': self.new_content})

    def test_create_workflow(self):
        """ Use the 'create' command, local changes are reflected in the cache """
        self.t.run("create . {}".format(self.reference))
        self.assertIn(">>>> I'm {}".format(self.reference), self.t.out)
        self.assertIn(">>>> content: {}".format(self.new_content), self.t.out)

    def test_install_workflow(self):
        """ Using the install command, it won't be taken into account """
        t2 = TestClient(cache_folder=self.t.cache_folder)
        t2.save({'conanfile.txt': "[requires]\n{}".format(self.reference)})
        ref = ConanFileReference.loads(self.reference)
        t2.run("install . --build={}".format(ref.name))
        self.assertNotIn(self.new_content, t2.out)
        self.assertIn(">>>> I'm {}".format(self.reference), self.t.out)
        self.assertIn(">>>> content: {}".format(self.reference), self.t.out)
