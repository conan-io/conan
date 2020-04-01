# coding=utf-8

import textwrap
import unittest

from parameterized.parameterized import parameterized_class

from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient, create_local_git_repo
from conans.util.files import load


@parameterized_class([{"verify_ssl": True}, {"verify_ssl": False},
                      {"verify_ssl": None},{"verify_ssl": "None"}, ])
class GitVerifySSLTestCase(unittest.TestCase):
    conanfile = textwrap.dedent("""
        from conans import ConanFile

        class Lib(ConanFile):
            scm = {{"type": "git", "url": "auto", "revision": "auto", {verify_ssl_attrib} }}

    """)

    ref = ConanFileReference.loads("name/version@user/channel")

    def setUp(self):
        self.client = TestClient()

        # Create a local repo
        verify_ssl_attrib_str = ""
        if self.verify_ssl is not None:
            verify_ssl_attrib_str = '"verify_ssl": {}'.format(self.verify_ssl)
        files = {'conanfile.py': self.conanfile.format(verify_ssl_attrib=verify_ssl_attrib_str)}
        url, _ = create_local_git_repo(files=files, commits=4, tags=['v0', ])
        self.client.run_command('git clone "{}" .'.format(url))

    def test_export(self):
        # Check the shallow value is substituted with the proper value
        self.client.run("export . {}".format(self.ref))
        content = load(self.client.cache.package_layout(self.ref).conanfile())
        if self.verify_ssl in [None, True, "None"]:
            self.assertNotIn("verify_ssl", content)
        else:
            self.assertIn('"verify_ssl": False', content)

        self.client.run("inspect {} -a scm".format(self.ref))  # Check we get a loadable conanfile.py
