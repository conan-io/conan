import os
import tempfile
import textwrap
import unittest

import pytest
import yaml

from conans.client.loader import ConanFileLoader
from conans.util.env import environment_update
from conans.model.recipe_ref import RecipeReference
from conans.paths import DATA_YML
from conans.test.utils.tools import TestClient
from conans.util.files import load
from conans.util.files import save_files


class SCMDataToConanDataTestCase(unittest.TestCase):
    ref = RecipeReference.loads("name/version@")

    def test_save_special_chars(self):
        conanfile = textwrap.dedent("""
            import os
            from conan import ConanFile

            class Recipe(ConanFile):
                scm = {"type": "git", "url": 'weir"d', "revision": "auto",
                       "subfolder": "weir\\"d", "submodule": "don't"}
        """)
        t = TestClient()
        t.save({'conanfile.py': conanfile})
        commit = t.init_git_repo()
        t.run("export . --name=name --version=version")

        # Check exported files
        ref_layout = t.get_latest_ref_layout(self.ref)
        exported_conanfile = load(ref_layout.conanfile())
        self.assertEqual(exported_conanfile, conanfile)
        exported_conandata = load(ref_layout.conandata())
        conan_data = yaml.safe_load(exported_conandata)
        self.assertDictEqual(conan_data['.conan']['scm'], {"type": "git", "url": 'weir"d',
                                                           "revision": commit,
                                                           "subfolder": "weir\"d",
                                                           "submodule": "don't"})

    @pytest.mark.tool("git")
    def test_auto_is_replaced(self):
        conanfile = textwrap.dedent("""
            import os
            from conan import ConanFile

            class Recipe(ConanFile):
                scm = {"type": "git", "url": "auto", "revision": "auto"}
        """)
        t = TestClient()
        commit = t.init_git_repo({'conanfile.py': conanfile})
        t.run_command('git remote add origin https://myrepo.com.git')
        t.run("export . --name=name --version=version")

        # Check exported files
        ref_layout = t.get_latest_ref_layout(self.ref)
        exported_conanfile = load(ref_layout.conanfile())
        self.assertEqual(exported_conanfile, conanfile)
        exported_conandata = load(ref_layout.conandata())
        conan_data = yaml.safe_load(exported_conandata)
        self.assertDictEqual(conan_data['.conan']['scm'],
                             {"type": "git", "url": 'https://myrepo.com.git', "revision": commit})

    def test_existing_field(self):
        conanfile = textwrap.dedent("""
            import os
            from conan import ConanFile

            class Recipe(ConanFile):
                scm = {"type": "git", "url": "myurl", "revision": "auto",
                       "username": "myuser", "password": os.environ.get("SECRET", None),}
        """)
        t = TestClient()
        t.save({'conanfile.py': conanfile,
                DATA_YML: yaml.safe_dump({'.conan': {'scm_data': {}}}, default_flow_style=False)})
        t.init_git_repo()

        # It fails with it activated
        t.run("export . --name=name --version=version", assert_error=True)
        self.assertIn("ERROR: Field '.conan' inside 'conandata.yml' file is"
                      " reserved to Conan usage.", t.out)

    @pytest.mark.tool("git")
    def test_empty_conandata(self):
        # https://github.com/conan-io/conan/issues/8209
        conanfile = textwrap.dedent("""
            from conan import ConanFile

            class Recipe(ConanFile):
                scm = {"type": "git", "url": "auto", "revision": "auto"}
            """)
        t = TestClient()
        commit = t.init_git_repo({'conanfile.py': conanfile,
                                  'conandata.yml': ""})
        t.run_command('git remote add origin https://myrepo.com.git')
        t.run("export . --name=name --version=version")

        # Check exported files
        ref_layout = t.get_latest_ref_layout(self.ref)
        exported_conanfile = load(ref_layout.conanfile())
        self.assertEqual(exported_conanfile, conanfile)
        exported_conandata = load(ref_layout.conandata())
        conan_data = yaml.safe_load(exported_conandata)
        self.assertDictEqual(conan_data['.conan']['scm'],
                             {"type": "git", "url": 'https://myrepo.com.git', "revision": commit})


class ParseSCMFromConanDataTestCase(unittest.TestCase):
    loader = ConanFileLoader()

    def test_parse_data(self):
        conanfile = textwrap.dedent("""
            import os
            from conan import ConanFile

            class Recipe(ConanFile):
                scm = {"type": "git", "url": "auto", "revision": "auto"}
        """)
        conan_data = {
            'something_else': {},
            '.conan': {'scm': {
                'type': 'git',
                'url': 'http://myrepo.com',
                'shallow': False,
                'revision': 'abcdefghijk'
            }}}
        test_folder = tempfile.mkdtemp()
        save_files(test_folder, {'conanfile.py': conanfile,
                                 DATA_YML: yaml.safe_dump(conan_data, default_flow_style=False)})

        conanfile_path = os.path.join(test_folder, 'conanfile.py')
        conanfile, _ = self.loader.load_basic_module(conanfile_path=conanfile_path)
        self.assertDictEqual(conanfile.scm, conan_data['.conan']['scm'])


@pytest.mark.tool("git")
def test_auto_can_be_automated():
    # https://github.com/conan-io/conan/issues/8881
    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import load, save

        class Recipe(ConanFile):

            def export(self):
                self.output.info("executing export")
                revision = os.getenv("USER_EXTERNAL_COMMIT")
                if revision is not None:
                    path = os.path.join(self.export_folder, "conandata.yml")
                    conandata = load(self, path)
                    conandata = conandata.replace("123", revision)
                    save(self, path, conandata)

            def source(self):
                self.output.info("USING COMMIT: {}".format(self.conan_data["commit"]))
    """)
    t = TestClient()
    t.save({'conanfile.py': conanfile,
            "conandata.yml": "commit: 123"})
    t.run("create . --name=pkg --version=1.0")
    assert "pkg/1.0: USING COMMIT: 123" in t.out

    with environment_update({"USER_EXTERNAL_COMMIT": "456"}):
        t.run("create . --name=pkg --version=1.0")
        assert "pkg/1.0: USING COMMIT: 456" in t.out

