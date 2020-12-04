# coding=utf-8
import platform
import textwrap
import unittest

import pytest
import six
from nose.plugins.attrib import attr

from conans.test.utils.tools import TestClient


@attr("toolchain")
@pytest.mark.toolchain
class BasicTest(unittest.TestCase):

    def test_basic(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            from conan.tools.cmake import CMakeToolchain
            class Pkg(ConanFile):
                def generate(self):
                    tc = CMakeToolchain(self)
                    tc.generate()
                """)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("install .")

        self.assertIn("conanfile.py: Calling generate()", client.out)
        toolchain = client.load("conan_toolchain.cmake")
        self.assertIn("Conan automatically generated toolchain file", toolchain)

    def test_declarative(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                settings = "os", "compiler", "arch", "build_type"
                generators = "CMakeToolchain", "MesonToolchain", "MakeToolchain", "MSBuildToolchain"
            """)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("install .")

        self.assertIn("conanfile.py: Generator 'CMakeToolchain' calling 'generate()'", client.out)
        self.assertIn("conanfile.py: Generator 'MesonToolchain' calling 'generate()'", client.out)
        self.assertIn("conanfile.py: Generator 'MakeToolchain' calling 'generate()'", client.out)
        self.assertIn("conanfile.py: Generator 'MSBuildToolchain' calling 'generate()'", client.out)
        toolchain = client.load("conan_toolchain.cmake")
        self.assertIn("Conan automatically generated toolchain file", toolchain)
        toolchain = client.load("conantoolchain.props")
        self.assertIn("<?xml version", toolchain)
        toolchain = client.load("conan_toolchain.mak")
        self.assertIn("# Conan generated toolchain file", toolchain)
        toolchain = client.load("conan_meson_native.ini")
        self.assertIn("[project options]", toolchain)

    def test_error_missing_settings(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                generators = "MSBuildToolchain"
            """)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("install .", assert_error=True)
        self.assertIn("Error in generator 'MSBuildToolchain': 'settings.build_type' doesn't exist",
                      client.out)

    def test_error_missing_settings_method(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            from conan.tools.microsoft import MSBuildToolchain
            class Pkg(ConanFile):
                def generate(self):
                   tc = MSBuildToolchain(self)
                   tc.generate()
            """)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("install .", assert_error=True)
        self.assertIn("ERROR: conanfile.py: Error in generate() method, line 7", client.out)

    def test_declarative_new_helper(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            from conan.tools.cmake import CMake
            class Pkg(ConanFile):
                generators = "CMakeToolchain"
                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
            """)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("install .")
        client.run("build .", assert_error=True)  # No CMakeLists.txt
        self.assertIn('-DCMAKE_TOOLCHAIN_FILE="conan_toolchain.cmake"',  client.out)
        self.assertIn("ERROR: conanfile.py: Error in build() method", client.out)

    @unittest.skipIf(six.PY2, "The import to sibling fails in Python2")
    def test_old_cmake_tools_imports(self):
        conanfile = textwrap.dedent("""
           from conans import ConanFile, CMakeToolchain, CMake
           class Pkg(ConanFile):
               def generate(self):
                   tc = CMakeToolchain(self)
                   tc.generate()
               def build(self):
                   cmake = CMake(self)
                   cmake.configure()
           """)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("install .")
        self.assertIn("'from conans import CMakeToolchain' has been deprecated and moved",
                      client.out)
        client.run("build .", assert_error=True)  # No CMakeLists.txt
        self.assertIn("This 'CMake' build helper has been deprecated and moved.", client.out)
        self.assertIn('-DCMAKE_TOOLCHAIN_FILE="conan_toolchain.cmake"', client.out)
        self.assertIn("ERROR: conanfile.py: Error in build() method", client.out)

    @unittest.skipIf(six.PY2, "The import to sibling fails in Python2")
    @unittest.skipUnless(platform.system() == "Windows", "msbuild requires Windows")
    def test_old_msbuild_tools_imports(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile, MSBuildToolchain, MSBuild
            class Pkg(ConanFile):
                settings = "os", "compiler", "arch", "build_type"
                def generate(self):
                   tc = MSBuildToolchain(self)
                   tc.generate()
                def build(self):
                   msbuild = MSBuild(self)
                   msbuild.build("Project.sln")
            """)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("install .")
        self.assertIn("'from conans import MSBuildToolchain' has been deprecated and moved",
                      client.out)
        client.run("build .", assert_error=True)  # No CMakeLists.txt
        self.assertIn("This 'MSBuild' build helper has been deprecated and moved.", client.out)
        self.assertIn("ERROR: conanfile.py: Error in build() method", client.out)

    @unittest.skipIf(six.PY2, "The import to sibling fails in Python2")
    def test_old_gnu_tools_imports(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile, MakeToolchain
            class Pkg(ConanFile):
                settings = "os", "compiler", "arch", "build_type"
                def generate(self):
                   tc = MakeToolchain(self)
                   tc.generate()
            """)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("install .")
        self.assertIn("'from conans import MakeToolchain' has been deprecated and moved",
                      client.out)

    @unittest.skipIf(six.PY2, "The import to sibling fails in Python2")
    def test_old_write_toolchain_files(self):
        conanfile = textwrap.dedent("""
               from conans import ConanFile
               from conan.tools.gnu import MakeToolchain
               from conan.tools.cmake import CMakeToolchain
               from conan.tools.microsoft import MSBuildToolchain
               class Pkg(ConanFile):
                   settings = "os", "compiler", "arch", "build_type"
                   def generate(self):
                      tc = MakeToolchain(self)
                      tc.write_toolchain_files()
                      tc = CMakeToolchain(self)
                      tc.write_toolchain_files()
                      tc = MSBuildToolchain(self)
                      tc.write_toolchain_files()
               """)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("install .")
        self.assertEqual(3, str(client.out).count("'write_toolchain_files()' "
                                                  "has been deprecated and moved"))

    def test_old_toolchain(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                toolchain = "cmake"
            """)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("install .")
        self.assertIn("The 'toolchain' attribute or method has been deprecated", client.out)

    def test_old_toolchain_method(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                def toolchain(self):
                    pass
            """)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("install .")
        self.assertIn("The 'toolchain' attribute or method has been deprecated", client.out)

    def test_toolchain_windows(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            from conan.tools.microsoft import MSBuildToolchain
            class Pkg(ConanFile):
                name = "Pkg"
                version = "0.1"
                settings = "os", "compiler", "arch", "build_type"
                generators = "msbuild"

                def generate(self):
                    tc = MSBuildToolchain(self)
                    tc.generate()
        """)

        client.save({"conanfile.py": conanfile})

        client.run('install . -s os=Windows -s compiler="Visual Studio" -s compiler.version=15'
                   ' -s compiler.runtime=MD')

        conan_toolchain_props = client.load("conantoolchain.props")
        self.assertIn("<ConanPackageName>Pkg</ConanPackageName>", conan_toolchain_props)
        self.assertIn("<ConanPackageVersion>0.1</ConanPackageVersion>", conan_toolchain_props)
