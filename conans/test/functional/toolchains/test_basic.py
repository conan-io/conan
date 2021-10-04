import os
import platform
import textwrap
import unittest

import pytest

from conans.test.utils.tools import TestClient
from conans.util.files import save


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
                generators = ("CMakeToolchain", "CMakeDeps", "MesonToolchain")
            """)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("install .")

        self.assertIn("conanfile.py: Generator 'CMakeToolchain' calling 'generate()'", client.out)
        self.assertIn("conanfile.py: Generator 'MesonToolchain' calling 'generate()'", client.out)
        self.assertIn("conanfile.py: Generator 'CMakeDeps' calling 'generate()'", client.out)
        toolchain = client.load("conan_toolchain.cmake")
        self.assertIn("Conan automatically generated toolchain file", toolchain)
        toolchain = client.load("conan_meson_native.ini")
        self.assertIn("[project options]", toolchain)

    @pytest.mark.tool_visual_studio
    @pytest.mark.skipif(platform.system() != "Windows", reason="Only for windows")
    def test_declarative_msbuildtoolchain(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                settings = "os", "compiler", "arch", "build_type"
                generators = ("MSBuildToolchain", )
            """)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("install .")

        self.assertIn("conanfile.py: Generator 'MSBuildToolchain' calling 'generate()'", client.out)
        toolchain = client.load("conantoolchain.props")
        self.assertIn("<?xml version", toolchain)

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
        self.assertIn("ERROR: conanfile.py: Error in generate() method, line 6", client.out)

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
        toolchain_path = os.path.join(client.current_folder,
                                      "conan_toolchain.cmake").replace("\\", "/")
        self.assertIn('-DCMAKE_TOOLCHAIN_FILE="{}"'.format(toolchain_path),  client.out)
        self.assertIn("ERROR: conanfile.py: Error in build() method", client.out)

    def test_old_toolchain(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                toolchain = "cmake"
            """)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("install .", assert_error=True)
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
        client.run("install .", assert_error=True)
        self.assertIn("The 'toolchain' attribute or method has been deprecated", client.out)

    @pytest.mark.tool_visual_studio
    @pytest.mark.skipif(platform.system() != "Windows", reason="Only for windows")
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

    def test_conflict_user_generator(self):
        client = TestClient()
        generator = textwrap.dedent("""
            from conans import ConanFile
            from conans.model import Generator
            class CMakeToolchain(Generator):
                @property
                def filename(self):
                    return "mygenerator.gen"
                @property
                def content(self):
                    return "HelloWorld"
                """)

        save(os.path.join(client.cache.generators_path, "mygenerator.py"), generator)
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class Pkg(ConanFile):
                settings = "os", "compiler", "arch", "build_type"
                generators = "CMakeToolchain"
            """)

        client.save({"conanfile.py": conanfile})
        client.run("install .")
        self.assertIn("Your custom generator name 'CMakeToolchain' is colliding", client.out)
        gen = client.load("mygenerator.gen")
        self.assertEqual("HelloWorld", gen)
