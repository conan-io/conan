# coding=utf-8

import platform
import unittest

from conans import ConanFile, Settings
from conans.client.generators.virtualenv import VirtualEnvGenerator
from conans.model.env_info import EnvValues
from conans.test.utils.tools import TestBufferConanOutput


class VirtualEnvGeneratorTest(unittest.TestCase):
    """ Verify VirtualEnvGenerator functions, functionality is tested
        in ~/conans/test/functional/generators/virtualenv_test.py
    """

    activate_sh = "activate.sh"
    activate_bat = "activate.bat"
    activate_ps1 = "activate.ps1"

    @classmethod
    def setUpClass(cls):
        env = EnvValues()
        env.add("USER_FLAG", "user_value")
        env.add("CL", ["cl1", "cl2"])
        env.add("PATH", ["another_path", ])
        env.add("PATH2", ["p1", "p2"])
        conanfile = ConanFile(TestBufferConanOutput(), None)
        conanfile.initialize(Settings({}), env)

        cls.generator = VirtualEnvGenerator(conanfile)
        cls.result = cls.generator.content

    def test_output(self):
        keys = ["deactivate.sh", "activate.sh"]
        if platform.system() == "Windows":
            keys += ["activate.bat", "deactivate.bat", "activate.ps1", "deactivate.ps1"]

        self.assertListEqual(sorted(keys), sorted(self.result.keys()))

    def test_variable(self):
        self.assertIn("USER_FLAG=\"user_value\"", self.result[self.activate_sh])

    def test_list_variable(self):
        self.assertIn("PATH=\"another_path\"${PATH+:$PATH}", self.result[self.activate_sh])
        self.assertIn("PATH2=\"p1\":\"p2\"${PATH2+:$PATH2}", self.result[self.activate_sh])

        if platform.system() == "Windows":
            self.assertIn("PATH=another_path;%PATH%", self.result[self.activate_bat])
            self.assertIn('$env:PATH2 = "p1;p2;$env:PATH2"', self.result[self.activate_ps1])

            self.assertIn("PATH=another_path;%PATH%", self.result[self.activate_bat])
            self.assertIn('$env:PATH2 = "p1;p2;$env:PATH2"', self.result[self.activate_ps1])

    def test_list_with_spaces(self):
        self.assertIn("CL", VirtualEnvGenerator.append_with_spaces)
        self.assertIn("CL=\"cl1 cl2 ${CL+ $CL}\"", self.result[self.activate_sh])

        if platform.system() == "Windows":
            self.assertIn("CL=cl1 cl2 %CL%", self.result[self.activate_bat])
            self.assertIn('$env:CL = "cl1 cl2 $env:CL"', self.result[self.activate_ps1])
