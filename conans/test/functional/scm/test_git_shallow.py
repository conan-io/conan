import textwrap
import unittest

import pytest
from parameterized import parameterized
from parameterized.parameterized import parameterized_class

from conans.model.recipe_ref import RecipeReference
from conans.test.utils.scm import create_local_git_repo
from conans.test.utils.tools import TestClient
from conans.util.files import load


def test_shallow_none_string():
    client = TestClient()
    client.save({'conanfile.py': textwrap.dedent("""
        from conans import ConanFile

        class Recipe(ConanFile):
            scm = {"type": "git", "url": "https://github.com/repo/library.git",
                    "revision": "123456", "shallow": 'None' }
    """)})

    client.run('export . --name=name --version=version', assert_error=True)
    assert "ERROR: SCM value for 'shallow' must be of type 'bool' (found 'str')" in str(client.out)


@pytest.mark.tool_git
@parameterized_class([{"shallow": True}, {"shallow": False},
                      {"shallow": None},  # No value written in the recipe
                      {"shallow": 'None'}])  # Explicit 'None' written in the recipe
class GitShallowTestCase(unittest.TestCase):
    conanfile = textwrap.dedent("""
        from conans import ConanFile
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

    # FIXME : https://github.com/conan-io/conan/issues/8449
    # scm_to_conandata=1 changes behavior for shallow=None
    @pytest.mark.xfail
    @parameterized.expand([("c6cc15fa2f4b576bd", False), ("0.22.1", True)])
    def test_remote_build(self, revision, shallow_works):
        # Shallow works only with branches or tags
        # xfail doesn't work (don't know why), just skip manually
        if self.shallow is "None" and revision == "0.22.1":
            return
        client = TestClient()
        client.save({'conanfile.py':
                         self.conanfile.format(shallow_attrib=self._shallow_attrib_str(),
                                               url="https://github.com/conan-io/conan.git",
                                               rev=revision)})

        client.run(f"create . --name={self.ref.name} --version={self.ref.version} --user={self.ref.user} --channel={self.ref.channel}")

        if self.shallow in [None, True] and shallow_works:
            self.assertIn(">>> describe-fails", client.out)
        else:
            self.assertIn(">>> tags: 0.22.1", client.out)
