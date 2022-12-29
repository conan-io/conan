# coding=utf-8
import os
import textwrap
import unittest

import pytest
from parameterized.parameterized import parameterized_class

from conans.model.ref import ConanFileReference
from conans.paths import DATA_YML
from conans.test.utils.scm import create_local_git_repo
from conans.test.utils.tools import TestClient
from conans.util.files import load


@pytest.mark.parametrize("scm_to_conandata", [True, False])
def test_verify_ssl_none_string(scm_to_conandata):
    client = TestClient()
    client.run("config set general.scm_to_conandata={}".format('1' if scm_to_conandata else '0'))
    client.save({'conanfile.py': textwrap.dedent("""
        from conans import ConanFile

        class Recipe(ConanFile):
            scm = {"type": "git", "url": "https://github.com/repo/library.git",
                    "revision": "123456", "verify_ssl": 'None' }
    """)})

    client.run('export . name/version@', assert_error=True)
    assert "ERROR: SCM value for 'verify_ssl' must be of type " \
           "'bool' (found 'str')" in str(client.out)


@pytest.mark.tool_git
@parameterized_class([{"verify_ssl": True}, {"verify_ssl": False},
                      {"verify_ssl": None},  # No value written in the recipe
                      {"verify_ssl": 'None'}])  # Explicit 'None' written in the recipe
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

    def _check_info_values(self, client):
        client.run("inspect {} -a scm".format(self.ref))  # Check we get a loadable conanfile.py
        if self.verify_ssl in [None]:
            self.assertNotIn('verify_ssl', str(client.out))
        elif self.verify_ssl in [True]:  # This is the default value
            not_appears = 'verify_ssl' not in str(client.out)
            value_explicit = 'verify_ssl: True' in str(client.out)
            self.assertTrue(not_appears or value_explicit)
        elif self.verify_ssl in ['None']:
            self.assertIn('verify_ssl: None', str(client.out))
        else:
            self.assertIn('verify_ssl: False', str(client.out))

    def test_export_scm_substituted(self):
        # Check the verify_ssl value is substituted with the proper value
        self.client.run("config set general.scm_to_conandata=0")
        self.client.run("export . {}".format(self.ref))
        content = load(self.client.cache.package_layout(self.ref).conanfile())
        if self.verify_ssl in [None, True]:
            self.assertNotIn("verify_ssl", content)
        elif self.verify_ssl in ['None']:
            self.assertIn('"verify_ssl": None', content)
        else:
            self.assertIn('"verify_ssl": False', content)

        self._check_info_values(self.client)

    def test_export_scm_to_conandata(self):
        # Check the verify_ssl value is stored and propagated with the proper value
        self.client.run("config set general.scm_to_conandata=1")
        self.client.run("export . {}".format(self.ref))
        content = load(os.path.join(self.client.cache.package_layout(self.ref).export(), DATA_YML))
        if self.verify_ssl in [None, True]:
            self.assertNotIn('verify_ssl', content)
        elif self.verify_ssl in ['None']:
            self.assertIn('verify_ssl: null', content)
        else:
            self.assertIn('verify_ssl: false', content)

        self._check_info_values(self.client)
