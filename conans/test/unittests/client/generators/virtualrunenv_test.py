# coding=utf-8

import platform
import unittest

from conans.client.generators.virtualrunenv import VirtualRunEnvGenerator
from conans.test.utils.conanfile import ConanFileMock


class VirtualRunEnvGeneratorTest(unittest.TestCase):

    activate_sh = "activate_run.sh"
    activate_bat = "activate_run.bat"
    activate_ps1 = "activate_run.ps1"

    @classmethod
    def setUpClass(cls):
        conanfile = ConanFileMock()
        conanfile.deps_cpp_info["hello"].bin_paths = ["bin1", "bin2"]
        conanfile.deps_cpp_info["hello"].lib_paths = ["lib1", "lib2"]

        cls.generator = VirtualRunEnvGenerator(conanfile)
        cls.result = cls.generator.content

    def test_output(self):
        keys = ["deactivate_run.sh", "activate_run.sh"]
        if platform.system() == "Windows":
            keys += ["activate_run.bat", "deactivate_run.bat",
                     "activate_run.ps1", "deactivate_run.ps1"]

        self.assertListEqual(sorted(keys), sorted(self.result.keys()))

    def test_environment(self):
        self.assertEqual(self.generator.env["PATH"], ["bin1", "bin2"])
        self.assertEqual(self.generator.env["LD_LIBRARY_PATH"], ["lib1", "lib2"])
        self.assertEqual(self.generator.env["DYLD_LIBRARY_PATH"], ["lib1", "lib2"])

    def test_scripts(self):
        self.assertIn('DYLD_LIBRARY_PATH="lib1":"lib2"${DYLD_LIBRARY_PATH+:$DYLD_LIBRARY_PATH}',
                      self.result[self.activate_sh])
        self.assertIn('LD_LIBRARY_PATH="lib1":"lib2"${LD_LIBRARY_PATH+:$LD_LIBRARY_PATH}',
                      self.result[self.activate_sh])
        self.assertIn('PATH="bin1":"bin2"${PATH+:$PATH}', self.result[self.activate_sh])

        if platform.system() == "Windows":
            self.assertIn('DYLD_LIBRARY_PATH=lib1;lib2;%DYLD_LIBRARY_PATH%',
                          self.result[self.activate_bat])
            self.assertIn('LD_LIBRARY_PATH=lib1;lib2;%LD_LIBRARY_PATH%',
                          self.result[self.activate_bat])
            self.assertIn('PATH=bin1;bin2;%PATH%', self.result[self.activate_bat])

            self.assertIn('$env:DYLD_LIBRARY_PATH = "lib1;lib2;$env:DYLD_LIBRARY_PATH"',
                          self.result[self.activate_ps1])
            self.assertIn('$env:LD_LIBRARY_PATH = "lib1;lib2;$env:LD_LIBRARY_PATH"',
                          self.result[self.activate_ps1])
            self.assertIn('$env:PATH = "bin1;bin2;$env:PATH"', self.result[self.activate_ps1])
