# coding=utf-8

import platform
import unittest

from conans.client.generators.virtualrunenv import VirtualRunEnvGenerator
from conans.test.utils.mocks import ConanFileMock


class VirtualRunEnvGeneratorTest(unittest.TestCase):

    activate_sh = "activate_run.sh"
    activate_bat = "activate_run.bat"
    activate_ps1 = "activate_run.ps1"
    environment_sh_env = "environment_run.sh.env"
    environment_bat_env = "environment_run.bat.env"
    environment_ps1_env = "environment_run.ps1.env"

    @classmethod
    def setUpClass(cls):
        conanfile = ConanFileMock()
        conanfile.deps_cpp_info["hello"].bin_paths = ["bin1", "bin2"]
        conanfile.deps_cpp_info["hello"].lib_paths = ["lib1", "lib2"]

        cls.generator = VirtualRunEnvGenerator(conanfile)
        cls.generator.output_path = "not-used"
        cls.result = cls.generator.content

    def test_output(self):
        keys = ["deactivate_run.sh", "activate_run.sh", self.environment_sh_env,
                "activate_run.ps1", "deactivate_run.ps1", self.environment_ps1_env]
        if platform.system() == "Windows":
            keys += ["activate_run.bat", "deactivate_run.bat", self.environment_bat_env]

        self.assertListEqual(sorted(keys), sorted(self.result.keys()))

    def test_environment(self):
        self.assertEqual(self.generator.env["PATH"], ["bin1", "bin2"])
        self.assertEqual(self.generator.env["LD_LIBRARY_PATH"], ["lib1", "lib2"])
        self.assertEqual(self.generator.env["DYLD_LIBRARY_PATH"], ["lib1", "lib2"])

    def test_scripts(self):
        content = self.result[self.environment_sh_env]
        self.assertIn('DYLD_LIBRARY_PATH="lib1":"lib2"${DYLD_LIBRARY_PATH:+:$DYLD_LIBRARY_PATH}',
                      content)
        self.assertIn('LD_LIBRARY_PATH="lib1":"lib2"${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}', content)
        self.assertIn('PATH="bin1":"bin2"${PATH:+:$PATH}', content)

        if platform.system() == "Windows":
            content = self.result[self.environment_bat_env]
            self.assertIn('DYLD_LIBRARY_PATH=lib1;lib2;%DYLD_LIBRARY_PATH%', content)
            self.assertIn('LD_LIBRARY_PATH=lib1;lib2;%LD_LIBRARY_PATH%', content)
            self.assertIn('PATH=bin1;bin2;%PATH%', content)

            content = self.result[self.environment_ps1_env]
            self.assertIn('DYLD_LIBRARY_PATH=lib1;lib2;$env:DYLD_LIBRARY_PATH', content)
            self.assertIn('LD_LIBRARY_PATH=lib1;lib2;$env:LD_LIBRARY_PATH', content)
            self.assertIn('PATH=bin1;bin2;$env:PATH', content)
        else:
            content = self.result[self.environment_ps1_env]
            self.assertIn('DYLD_LIBRARY_PATH=lib1:lib2:$env:DYLD_LIBRARY_PATH', content)
            self.assertIn('LD_LIBRARY_PATH=lib1:lib2:$env:LD_LIBRARY_PATH', content)
            self.assertIn('PATH=bin1:bin2:$env:PATH', content)
