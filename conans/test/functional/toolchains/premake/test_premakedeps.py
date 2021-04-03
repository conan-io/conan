import pytest
import textwrap
import unittest

from conans.test.assets.cpp_test_files import cpp_hello_conan_files
from conans.test.assets.sources import gen_function_cpp
from conans.test.utils.tools import TestClient

premake_file = r"""
workspace("ConanPremakeDemo")

    configurations { "Debug", "Release" }

    project "ConanPremakeDemo"
        kind "ConsoleApp"
        language "C++"
        targetdir "bin/%{cfg.buildcfg}"

        linkoptions { conan_exelinkflags }

        files { "**.h", "**.cpp" }

        --filter "configurations:Debug"
        --    require('conanbuildinfo_debug.premake').conan_basic_setup()
        --    defines { "DEBUG" }
        --    symbols "On"
        filter "configurations:Release"
            require('conanbuildinfo_release.premake').conan_basic_setup()
            defines { "NDEBUG" }
            optimize "On"
"""


@pytest.mark.tool_premake
class PremakeGeneratorTest(unittest.TestCase):

    def test_premake_generator(self):
        client = TestClient()
        # TODO: replace with more modern GenConanfile and others
        files = cpp_hello_conan_files("Hello0", "1.0")
        client.save(files)
        client.run("create . ")
        files = cpp_hello_conan_files("Hello3", "1.0")
        client.save(files, clean_first=True)
        client.run("create . ")
        files = cpp_hello_conan_files("Hello1", "1.0", deps=["Hello0/1.0"])
        client.save(files, clean_first=True)
        client.run("create . ")

        conanfile = textwrap.dedent("""
            from conans import ConanFile, MSBuild
            class HelloConan(ConanFile):
                settings = "os", "build_type", "compiler", "arch"
                requires = "Hello1/1.0", "Hello3/1.0"
                generators = "PremakeDeps"
                def build(self):
                    self.run('premake gmake2')
                    self.run('make config=release')
            """)

        myproject_cpp = gen_function_cpp(name="main", msg="MyProject", includes=["helloHello3"],
                                         calls=["helloHello3"])

        files = {"premake5.lua": premake_file,
                 "MyProject.cpp": myproject_cpp,
                 "conanfile.py": conanfile}

        client.save(files, clean_first=True)
        client.run("install .")
        client.run("build .")
        client.run_command(r"bin/Release/ConanPremakeDemo")
        self.assertIn("MyProject: Release!", client.out)
        self.assertIn("Hello Hello3", client.out)
        #client.run_command(r"x64\Release\MyApp.exe")
        #self.assertIn("MyApp: Release!", client.out)
        #self.assertIn("Hello Hello1", client.out)
        #self.assertIn("Hello Hello0", client.out)
