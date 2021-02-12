# coding=utf-8

import platform
import unittest

from conans.client.generators.virtualbuildenv import VirtualBuildEnvGenerator
from conans.test.utils.mocks import MockSettings, ConanFileMock


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
        cls.generator.output_path = "not-used"
        cls.result = cls.generator.content

    def test_output(self):
        keys = ["deactivate_build.sh", "activate_build.sh", "environment_build.sh.env",
                "activate_build.ps1", "deactivate_build.ps1", "environment_build.ps1.env"]
        if platform.system() == "Windows":
            keys += ["activate_build.bat", "deactivate_build.bat", "environment_build.bat.env"]

        self.assertListEqual(sorted(keys), sorted(self.result.keys()))

    def test_environment(self):
        self.assertEqual(self.generator.env["CFLAGS"], ['-O3', '-s', '--sysroot=/path/to/sysroot'])
        self.assertEqual(self.generator.env["CPPFLAGS"], ['-DNDEBUG'])
        self.assertEqual(self.generator.env["CXXFLAGS"], ['-O3', '-s', '--sysroot=/path/to/sysroot'])
        self.assertEqual(self.generator.env["LDFLAGS"], ['--sysroot=/path/to/sysroot'])
        self.assertEqual(self.generator.env["LIBS"], [])

    def test_scripts(self):
        content = self.result["environment_build.sh.env"]
        self.assertIn('CPPFLAGS="-DNDEBUG${CPPFLAGS:+ $CPPFLAGS}"', content)
        self.assertIn('CXXFLAGS="-O3 -s --sysroot=/path/to/sysroot${CXXFLAGS:+ $CXXFLAGS}"', content)
        self.assertIn('CFLAGS="-O3 -s --sysroot=/path/to/sysroot${CFLAGS:+ $CFLAGS}"', content)
        self.assertIn('LDFLAGS="--sysroot=/path/to/sysroot${LDFLAGS:+ $LDFLAGS}"', content)
        self.assertIn('LIBS="${LIBS:+ $LIBS}"', content)

        content = self.result["environment_build.ps1.env"]
        self.assertIn('CPPFLAGS=-DNDEBUG $env:CPPFLAGS', content)
        self.assertIn('CXXFLAGS=-O3 -s --sysroot=/path/to/sysroot $env:CXXFLAGS', content)
        self.assertIn('CFLAGS=-O3 -s --sysroot=/path/to/sysroot $env:CFLAGS', content)
        self.assertIn('LDFLAGS=--sysroot=/path/to/sysroot $env:LDFLAGS', content)
        self.assertIn('LIBS=$env:LIBS', content)

        if platform.system() == "Windows":
            content = self.result["environment_build.bat.env"]
            self.assertIn('CPPFLAGS=-DNDEBUG %CPPFLAGS%', content)
            self.assertIn('CXXFLAGS=-O3 -s --sysroot=/path/to/sysroot %CXXFLAGS%', content)
            self.assertIn('CFLAGS=-O3 -s --sysroot=/path/to/sysroot %CFLAGS%', content)
            self.assertIn('LDFLAGS=--sysroot=/path/to/sysroot %LDFLAGS%', content)
            self.assertIn('LIBS=%LIBS%', content)
