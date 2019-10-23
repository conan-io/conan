# coding=utf-8

import platform
import unittest

from conans.client.generators.virtualbuildenv import VirtualBuildEnvGenerator
from conans.test.utils.conanfile import ConanFileMock, MockSettings


class VirtualBuildEnvGeneratorGCCTest(unittest.TestCase):

    activate_sh = "activate_build.sh"
    activate_bat = "activate_build.bat"
    activate_ps1 = "activate_build.ps1"

    @classmethod
    def setUpClass(cls):
        conanfile = ConanFileMock()
        conanfile.settings = MockSettings({"compiler": "gcc",
                                           "build_type": "Release"})

        cls.generator = VirtualBuildEnvGenerator(conanfile)
        cls.result = cls.generator.content

    def test_output(self):
        keys = ["deactivate_build.sh", "activate_build.sh"]
        if platform.system() == "Windows":
            keys += ["activate_build.bat", "deactivate_build.bat",
                     "activate_build.ps1", "deactivate_build.ps1"]

        self.assertListEqual(sorted(keys), sorted(self.result.keys()))

    def test_environment(self):
        self.assertEqual(self.generator.env["CFLAGS"], ['-O3', '-s', '--sysroot=/path/to/sysroot'])
        self.assertEqual(self.generator.env["CPPFLAGS"], ['-DNDEBUG'])
        self.assertEqual(self.generator.env["CXXFLAGS"], ['-O3', '-s', '--sysroot=/path/to/sysroot'])
        self.assertEqual(self.generator.env["LDFLAGS"], ['--sysroot=/path/to/sysroot'])
        self.assertEqual(self.generator.env["LIBS"], [])

    def test_scripts(self):
        self.assertIn('CPPFLAGS="-DNDEBUG ${CPPFLAGS+ $CPPFLAGS}"', self.result[self.activate_sh])
        self.assertIn('CXXFLAGS="-O3 -s --sysroot=/path/to/sysroot ${CXXFLAGS+ $CXXFLAGS}"',
                      self.result[self.activate_sh])
        self.assertIn('CFLAGS="-O3 -s --sysroot=/path/to/sysroot ${CFLAGS+ $CFLAGS}"',
                      self.result[self.activate_sh])
        self.assertIn('LDFLAGS="--sysroot=/path/to/sysroot ${LDFLAGS+ $LDFLAGS}"',
                      self.result[self.activate_sh])
        self.assertIn('LIBS="${LIBS+ $LIBS}"', self.result[self.activate_sh])

        if platform.system() == "Windows":
            self.assertIn('SET CPPFLAGS=-DNDEBUG %CPPFLAGS%',
                          self.result[self.activate_bat])
            self.assertIn('SET CXXFLAGS=-O3 -s --sysroot=/path/to/sysroot %CXXFLAGS%',
                          self.result[self.activate_bat])
            self.assertIn('SET CFLAGS=-O3 -s --sysroot=/path/to/sysroot %CFLAGS%',
                          self.result[self.activate_bat])
            self.assertIn('SET LDFLAGS=--sysroot=/path/to/sysroot %LDFLAGS%',
                          self.result[self.activate_bat])
            self.assertIn('SET LIBS=%LIBS%', self.result[self.activate_bat])

            self.assertIn('$env:CPPFLAGS = "-DNDEBUG $env:CPPFLAGS"',
                          self.result[self.activate_ps1])
            self.assertIn('$env:CXXFLAGS = "-O3 -s --sysroot=/path/to/sysroot $env:CXXFLAGS"',
                          self.result[self.activate_ps1])
            self.assertIn('$env:CFLAGS = "-O3 -s --sysroot=/path/to/sysroot $env:CFLAGS"',
                          self.result[self.activate_ps1])
            self.assertIn('$env:LDFLAGS = "--sysroot=/path/to/sysroot $env:LDFLAGS"',
                          self.result[self.activate_ps1])
            self.assertIn('$env:LIBS = "$env:LIBS"', self.result[self.activate_ps1])
