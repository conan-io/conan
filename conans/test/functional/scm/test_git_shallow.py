# coding=utf-8

import textwrap
import unittest
import os

from parameterized.parameterized import parameterized_class
from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient, create_local_git_repo
from conans.util.files import load, rmdir


@parameterized_class([{"shallow": True}, {"shallow": False}, {"shallow": None}, ])
class GitShallowTestCase(unittest.TestCase):
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conans.errors import ConanException
        from six import StringIO
        
        class Lib(ConanFile):
            scm = {{"type": "git", "url": "auto", "revision": "auto", {shallow_attrib} }}
            
            def build(self):
                mybuf = StringIO()
                try:
                    out = self.run("git describe --tags", output=mybuf)
                    self.output.info(">>> tags: {{}}".format(mybuf.getvalue()))
                except ConanException:
                    pass
    """)

    ref = ConanFileReference.loads("name/version@user/channel")

    def setUp(self):
        self.client = TestClient()

        # Create a local repo
        shallow_attrib_str = ""
        if self.shallow is not None:
            shallow_attrib_str = '"shallow": {}'.format(self.shallow)
        files = {'conanfile.py': self.conanfile.format(shallow_attrib=shallow_attrib_str)}
        url, _ = create_local_git_repo(files=files, commits=4, tags=['v0', ])
        self.client.run_command('git clone "{}" .'.format(url))

    def test_export(self):
        # Check the shallow value is substituted with the proper value
        self.client.run("export . {}".format(self.ref))
        content = load(self.client.cache.package_layout(self.ref).conanfile())
        if self.shallow is None:
            self.assertNotIn("shallow", content)
        elif self.shallow:
            self.assertIn('"shallow": "True"', content)
        else:
            self.assertIn('"shallow": "False"', content)

        self.client.run("inspect {} -a scm".format(self.ref))  # Check we get a loadable conanfile.py

    def test_local_build(self):
        self.client.run("install . -if if")
        self.client.run("build . -if if -bf bf")

        self.assertIn(">>> tags: v0", self.client.out)

    def test_remote_build(self):
        self.client.run("export . {}".format(self.ref))
        os.unlink(self.client.cache.package_layout(self.ref).scm_folder())
        self.client.run("install {} --build".format(self.ref))

        if self.shallow is None or self.shallow:
            self.assertNotIn(">>> tags: v0", self.client.out)
        else:
            self.assertIn(">>> tags: v0", self.client.out)
