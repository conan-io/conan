# coding=utf-8

import textwrap
import unittest

import pytest
from parameterized.parameterized import parameterized_class

from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient
from conans.test.utils.scm import create_local_git_repo
from conans.util.files import load


@pytest.mark.tool_git
@parameterized_class([{"verify_ssl": True}, {"verify_ssl": False},
                      {"verify_ssl": None}, {"verify_ssl": "None"}, ])
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
        scm_info = self.client.scm_info_cache(self.ref)
        if self.verify_ssl in [None, True, "None"]:
            self.assertIsNone(scm_info.verify_ssl)
        else:
            self.assertEqual(scm_info.verify_ssl, False)

        self.client.run("inspect {} -a scm".format(self.ref))  # Check we get a loadable conanfile.py
