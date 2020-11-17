# coding=utf-8

import os
import platform
import textwrap
import unittest

from nose.plugins.attrib import attr

from conans.test.utils.tools import TestClient

@unittest.skipUnless(platform.system() == "Windows", "Requires MSBuild")
class MSBuildToolchainTest(unittest.TestCase):
  
    def test_toolchain_windows(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile, MSBuildToolchain
            class Pkg(ConanFile):
                name = "Pkg"
                version = "0.1"
                settings = "os", "compiler", "arch", "build_type"
                generators = "msbuild"

                def toolchain(self):
                    tc = MSBuildToolchain(self)
                    tc.write_toolchain_files()
        """)

        client.save({"conanfile.py": conanfile})

        client.run('install . -s os=Windows -s compiler="Visual Studio" -s compiler.version=15'
                   ' -s compiler.runtime=MD')

        conan_toolchain_props = client.load("conan_toolchain.props")
        self.assertIn("<ConanPackageName>Pk2g</ConanPackageName>", conan_toolchain_props)
        self.assertIn("<ConanPackageVersion>0.1</ConanPackageVersion>", conan_toolchain_props)
