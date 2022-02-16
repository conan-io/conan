import textwrap
import unittest

import pytest
from parameterized.parameterized import parameterized_class

from conans.model.recipe_ref import RecipeReference
from conans.test.utils.scm import create_local_git_repo
from conans.test.utils.tools import TestClient
from conans.util.files import load


def test_shallow_none_string():
    client = TestClient()
    client.save({'conanfile.py': textwrap.dedent("""
        from conan import ConanFile

        class Recipe(ConanFile):
            scm = {"type": "git", "url": "https://github.com/repo/library.git",
                    "revision": "auto", "shallow": 'None' }
    """)})

    client.run('export . --name=name --version=version', assert_error=True)
    assert "ERROR: SCM value for 'shallow' must be of type 'bool' (found 'str')" in str(client.out)


@pytest.mark.tool("git")
@parameterized_class([{"shallow": True}, {"shallow": False},
                      {"shallow": None},  # No value written in the recipe
                      {"shallow": 'None'}])  # Explicit 'None' written in the recipe
class GitShallowTestCase(unittest.TestCase):
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conans.errors import ConanException
        from io import StringIO

        class Lib(ConanFile):
            scm = {{"type": "git", "url": "{url}", "revision": "{rev}", {shallow_attrib} }}

            def build(self):
                try:
                    mybuf = StringIO()
                    out = self.run("git describe --tags", stdout=mybuf)
                    self.output.info(">>> tags: {{}}".format(mybuf.getvalue()))
                except ConanException:
                    self.output.info(">>> describe-fails")
    """)

    ref = RecipeReference.loads("name/version@user/channel")

    def _shallow_attrib_str(self):
        shallow_attrib_str = ""
        if self.shallow is not None:
            shallow_attrib_str = '"shallow": {}'.format(self.shallow)
        return shallow_attrib_str

    def test_export_scm_to_conandata(self):
        # Check the shallow value is stored and propagated with the proper value
        client = TestClient()
        files = {'conanfile.py': self.conanfile.format(shallow_attrib=self._shallow_attrib_str(),
                                                       url='auto', rev='auto')}
        url, _ = create_local_git_repo(files=files)
        client.run_command('git clone "{}" .'.format(url))

        client.run(f"export . --name={self.ref.name} --version={self.ref.version} --user={self.ref.user} --channel={self.ref.channel}")
        content = load(client.get_latest_ref_layout(self.ref).conandata())
        if self.shallow in [None, True]:
            self.assertNotIn('shallow', content)
        elif self.shallow in ['None']:
            self.assertIn('shallow: null', content)
        else:
            self.assertIn('shallow: false', content)
