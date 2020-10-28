import os
import textwrap
import unittest

from conans import Settings
from conans.client.graph.python_requires import ConanPythonRequire
from conans.client.loader import ConanFileLoader
from conans.model.env_info import EnvValues
from conans.model.profile import Profile
from conans.model.ref import ConanFileReference
from conans.test.utils.test_files import temp_folder
from conans.test.utils.mocks import TestBufferConanOutput
from conans.util.files import save


class LoadConanfileTxtTest(unittest.TestCase):

    def setUp(self):
        settings = Settings()
        self.profile = Profile()
        self.profile.processed_settings = settings

        output = TestBufferConanOutput()
        self.loader = ConanFileLoader(None, output, ConanPythonRequire(None, None))

    def test_env(self):
        env_values = EnvValues()
        env_values.add("PREPEND_PATH", ["hello", "bye"])
        env_values.add("VAR", ["var_value"])
        self.profile.env_values = env_values
        conanfile_txt_path = os.path.join(temp_folder(), "conanfile.txt")
        save(conanfile_txt_path, "")
        conanfile = self.loader.load_conanfile_txt(conanfile_txt_path, self.profile)
        self.assertEqual(conanfile.env, {"PREPEND_PATH": ["hello", "bye"], "VAR": ["var_value"]})

    def test_conanfile_py_env(self):
        conanfile_path = os.path.join(temp_folder(), "conanfile.py")
        env_values = EnvValues()
        env_values.add("PREPEND_PATH", ["hello", "bye"])
        env_values.add("VAR", ["var_value"])
        self.profile.env_values = env_values
        save(conanfile_path,
             textwrap.dedent("""
                from conans import ConanFile

                class TestConan(ConanFile):
                    name = "hello"
                    version = "1.0"
             """))
        ref = ConanFileReference("hello", "1.0", "user", "channel")
        conanfile = self.loader.load_conanfile(conanfile_path, self.profile, ref)
        self.assertEqual(conanfile.env, {"PREPEND_PATH": ["hello", "bye"], "VAR": ["var_value"]})
