# coding=utf-8

import platform
import unittest

from mock import Mock

from conans import ConanFile, Settings
from conans.client.generators.virtualenv import VirtualEnvGenerator
from conans.model.env_info import EnvValues


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
        env.add("PATH3", ["p1", "p2", "p1", "p3", "p4", "p2"])
        conanfile = ConanFile(Mock(), None)
        conanfile.initialize(Settings({}), env)

        cls.generator = VirtualEnvGenerator(conanfile)
        cls.generator.output_path = "not-used"
        cls.result = cls.generator.content

    def test_output(self):
        keys = ["deactivate.sh", "activate.sh", "environment.sh.env",
                "activate.ps1", "deactivate.ps1", "environment.ps1.env"]
        if platform.system() == "Windows":
            keys += ["activate.bat", "deactivate.bat", "environment.bat.env"]

        self.assertListEqual(sorted(keys), sorted(self.result.keys()))

    def test_variable(self):
        self.assertIn("USER_FLAG=\"user_value\"", self.result['environment.sh.env'])

    def test_list_variable(self):
        self.assertIn("PATH=\"another_path\"${PATH:+:$PATH}", self.result['environment.sh.env'])
        self.assertIn("PATH2=\"p1\":\"p2\"${PATH2:+:$PATH2}", self.result['environment.sh.env'])
        self.assertIn("PATH3=\"p1\":\"p2\":\"p3\":\"p4\"${PATH3:+:$PATH3}",
                      self.result['environment.sh.env'])

        if platform.system() == "Windows":
            self.assertIn("PATH=another_path;%PATH%", self.result["environment.bat.env"])
            self.assertIn('PATH2=p1;p2;%PATH2%', self.result["environment.bat.env"])

            self.assertIn("PATH=another_path;$env:PATH", self.result["environment.ps1.env"])
            self.assertIn('PATH2=p1;p2;$env:PATH2', self.result["environment.ps1.env"])
        else:
            self.assertIn('PATH=another_path:$env:PATH', self.result["environment.ps1.env"])
            self.assertIn('PATH2=p1:p2:$env:PATH2', self.result["environment.ps1.env"])

    def test_list_with_spaces(self):
        self.assertIn("CL", VirtualEnvGenerator.append_with_spaces)
        self.assertIn("CL=\"cl1 cl2${CL:+ $CL}\"", self.result['environment.sh.env'])
        self.assertIn('CL=cl1 cl2 $env:CL', self.result["environment.ps1.env"])

        if platform.system() == "Windows":
            self.assertIn("CL=cl1 cl2 %CL%", self.result["environment.bat.env"])
