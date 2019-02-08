import os
import textwrap
import unittest

from conans import Settings
from conans.client.graph.python_requires import ConanPythonRequire
from conans.client.loader import ConanFileLoader
from conans.model.env_info import EnvValues
from conans.model.profile import Profile
from conans.model.ref import ConanFileReference
from conans.test.utils.conanfile import MockSettings
from conans.test.utils.runner import TestRunner
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestBufferConanOutput
from conans.util.files import save


class LoadConanfileTxtTest(unittest.TestCase):

    def setUp(self):
        settings = Settings()
        self.profile = Profile()
        self.profile._settings = settings
        self.profile._user_options = None
        self.profile._env_values = None
        self.conanfile_txt_path = os.path.join(temp_folder(), "conanfile.txt")
        output = TestBufferConanOutput()
        self.loader = ConanFileLoader(TestRunner(output), output, None)

    def env_test(self):
        env_values = EnvValues()
        env_values.add("PREPEND_PATH", ["hello", "bye"])
        env_values.add("VAR", ["var_value"])
        self.profile._env_values = env_values
        save(self.conanfile_txt_path, "")
        conanfile = self.loader.load_conanfile_txt(self.conanfile_txt_path, self.profile)
        self.assertEquals(conanfile.env, {"PREPEND_PATH": ["hello", "bye"], "VAR": ["var_value"]})


class LoadConanfileTest(unittest.TestCase):

    def setUp(self):
        settings = Settings()
        self.profile = Profile()
        self.profile._settings = settings
        self.profile._user_options = None
        self.profile._env_values = None
        self.profile._dev_reference = None
        self.profile._package_settings = None
        self.conanfile_path = os.path.join(temp_folder(), "conanfile.py")
        output = TestBufferConanOutput()
        self.loader = ConanFileLoader(TestRunner(output), output, ConanPythonRequire(None, None))

    def env_test(self):
        env_values = EnvValues()
        env_values.add("PREPEND_PATH", ["hello", "bye"])
        env_values.add("VAR", ["var_value"])
        self.profile._env_values = env_values
        save(self.conanfile_path,
             textwrap.dedent("""
                from conans import ConanFile
                
                class TestConan(ConanFile):
                    name = "hello"
                    version = "1.0"
             """))
        ref = ConanFileReference("hello", "1.0", "user", "channel")
        conanfile = self.loader.load_conanfile(self.conanfile_path, self.profile, ref)
        self.assertEquals(conanfile.env, {"PREPEND_PATH": ["hello", "bye"], "VAR": ["var_value"]})
