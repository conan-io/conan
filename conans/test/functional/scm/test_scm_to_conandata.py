import os
import textwrap
import unittest

import yaml

from conans.model.ref import ConanFileReference
from conans.paths import DATA_YML
from conans.test.utils.tools import TestClient, create_local_git_repo
from conans.util.files import load, save_files
import codecs
import os
import shutil
import tempfile
import unittest
from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestBufferConanOutput, TestClient
import uuid

import six

from conans.client.cmd.export import _replace_scm_data_in_conanfile
from conans.client.graph.python_requires import ConanPythonRequire
from conans.client.loader import ConanFileLoader
from conans.test.utils.tools import try_remove_readonly
from conans.util.files import load


class SCMDataToConanDataTestCase(unittest.TestCase):
    ref = ConanFileReference.loads("name/version@")

    def test_plain_recipe(self):
        conanfile = textwrap.dedent("""
            import os
            from conans import ConanFile
            
            class Recipe(ConanFile):
                scm = {"type": "git", "url": "myurl", "revision": "myrev",
                       "username": "myuser", "password": os.environ.get("SECRET", None),}
        """)
        t = TestClient()
        t.save({'conanfile.py': conanfile})
        t.run("config set general.scm_to_conandata=1")
        t.run("export . name/version@")

        # Check exported files
        package_layout = t.cache.package_layout(self.ref)
        exported_conanfile = load(package_layout.conanfile())
        self.assertEqual(exported_conanfile, conanfile)
        exported_conandata = load(os.path.join(package_layout.export(), DATA_YML))
        conan_data = yaml.safe_load(exported_conandata)
        self.assertDictEqual(conan_data['.conan']['scm_data'], {"type": "git", "url": "myurl", "revision": "myrev"})

    def test_save_special_chars(self):
        conanfile = textwrap.dedent("""
            import os
            from conans import ConanFile

            class Recipe(ConanFile):
                scm = {"type": "git", "url": 'weir"d', "revision": 123,
                       "subfolder": "weir\\"d", "submodule": "don't"}
        """)
        t = TestClient()
        t.save({'conanfile.py': conanfile})
        t.run("config set general.scm_to_conandata=1")
        t.run("export . name/version@")

        # Check exported files
        package_layout = t.cache.package_layout(self.ref)
        exported_conanfile = load(package_layout.conanfile())
        self.assertEqual(exported_conanfile, conanfile)
        exported_conandata = load(os.path.join(package_layout.export(), DATA_YML))
        conan_data = yaml.safe_load(exported_conandata)
        self.assertDictEqual(conan_data['.conan']['scm_data'], {"type": "git", "url": 'weir"d', "revision": 123,
                                                                "subfolder": "weir\"d", "submodule": "don't"})

    def test_auto_is_replaced(self):
        conanfile = textwrap.dedent("""
            import os
            from conans import ConanFile

            class Recipe(ConanFile):
                scm = {"type": "git", "url": "auto", "revision": "auto"}
        """)
        t = TestClient()
        t.save({'conanfile.py': conanfile})
        _, commit = create_local_git_repo(folder=t.current_folder)
        t.run_command('git remote add origin https://myrepo.com.git')
        t.run("config set general.scm_to_conandata=1")
        t.run("export . name/version@")

        # Check exported files
        package_layout = t.cache.package_layout(self.ref)
        exported_conanfile = load(package_layout.conanfile())
        self.assertEqual(exported_conanfile, conanfile)
        exported_conandata = load(os.path.join(package_layout.export(), DATA_YML))
        conan_data = yaml.safe_load(exported_conandata)
        self.assertDictEqual(conan_data['.conan']['scm_data'], {"type": "git", "url": 'https://myrepo.com.git',
                                                                "revision": commit})

    def test_existing_field(self):
        conanfile = textwrap.dedent("""
            import os
            from conans import ConanFile

            class Recipe(ConanFile):
                scm = {"type": "git", "url": "myurl", "revision": "myrev",
                       "username": "myuser", "password": os.environ.get("SECRET", None),}
        """)
        t = TestClient()
        save_files({'conanfile.py': conanfile,
                DATA_YML: yaml.safe_dump({'.conan': {'scm_data': {}}}, default_flow_style=False)})

        # Without activating the behavior, it works
        t.run("export . name/version@")

        # It fails with it activated
        t.run("config set general.scm_to_conandata=1")
        t.run("export . name/version@", assert_error=True)
        self.assertIn("ERROR: Field '.conan' inside 'conandata.yml' file is reserved to Conan usage.", t.out)


class ParseSCMFromConanDataTestCase(unittest.TestCase):
    loader = ConanFileLoader(runner=None, output=TestBufferConanOutput(),
                             python_requires=ConanPythonRequire(None, None))

    def test_parse_data(self):
        conanfile = textwrap.dedent("""
            import os
            from conans import ConanFile

            class Recipe(ConanFile):
                scm = {"type": "git", "url": "auto", "revision": "auto"}
        """)
        conan_data = {
            'something_else': {},
            '.conan': {'scm_data': {
                'type': 'git',
                'url': 'http://myrepo.com',
                'shallow': False,
                'revision': 'abcdefghijk'
            }}}
        test_folder = tempfile.mkdtemp()
        save_files(test_folder, {'conanfile.py': conanfile,
                                 DATA_YML: yaml.safe_dump(conan_data, default_flow_style=False)})

        conanfile, _ = self.loader.load_basic_module(conanfile_path=os.path.join(test_folder, 'conanfile.py'))
        self.assertDictEqual(conanfile.scm, conan_data['.conan']['scm_data'])
