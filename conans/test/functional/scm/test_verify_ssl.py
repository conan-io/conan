import textwrap
import unittest

import pytest
from parameterized.parameterized import parameterized_class

from conans.model.recipe_ref import RecipeReference
from conans.test.utils.scm import create_local_git_repo
from conans.test.utils.tools import TestClient
from conans.util.files import load


def test_verify_ssl_none_string():
    client = TestClient()
    client.save({'conanfile.py': textwrap.dedent("""
        from conan import ConanFile

        class Recipe(ConanFile):
            scm = {"type": "git", "url": "https://github.com/repo/library.git",
                    "revision": "auto", "verify_ssl": 'None' }
    """)})

    client.run('export . --name=name --version=version', assert_error=True)
    assert "ERROR: SCM value for 'verify_ssl' must be of type " \
           "'bool' (found 'str')" in str(client.out)


@pytest.mark.tool("git")
@parameterized_class([{"verify_ssl": True}, {"verify_ssl": False},
                      {"verify_ssl": None},  # No value written in the recipe
                      {"verify_ssl": 'None'}])  # Explicit 'None' written in the recipe
class GitVerifySSLTestCase(unittest.TestCase):
    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class Lib(ConanFile):
            scm = {{"type": "git", "url": "auto", "revision": "auto", {verify_ssl_attrib} }}

    """)

    ref = RecipeReference.loads("name/version@user/channel")

    def setUp(self):
        self.client = TestClient()

        # Create a local repo
        verify_ssl_attrib_str = ""
        if self.verify_ssl is not None:
            verify_ssl_attrib_str = '"verify_ssl": {}'.format(self.verify_ssl)
        files = {'conanfile.py': self.conanfile.format(verify_ssl_attrib=verify_ssl_attrib_str)}
        url, _ = create_local_git_repo(files=files, commits=4, tags=['v0', ])
        self.client.run_command('git clone "{}" .'.format(url))

    def test_export_scm_to_conandata(self):
        # Check the verify_ssl value is stored and propagated with the proper value
        self.client.run(f"export . --name={self.ref.name} --version={self.ref.version} --user={self.ref.user} --channel={self.ref.channel}")
        content = load(self.client.get_latest_ref_layout(self.ref).conandata())
        if self.verify_ssl in [None, True]:
            self.assertNotIn('verify_ssl', content)
        elif self.verify_ssl in ['None']:
            self.assertIn('verify_ssl: null', content)
        else:
            self.assertIn('verify_ssl: false', content)
