import os
import textwrap
import unittest

from nose.plugins.attrib import attr

from conans import load
from conans.client.tools import which
from conans.test.utils.tools import TestClient


@attr("premake")
@unittest.skipIf(which("premake5") is None, "Needs premake5")
class PremakeGeneratorTest(unittest.TestCase):

    def setUp(self):
        self.client = TestClient()
        conanfile = textwrap.dedent("""
        [generators]
        premake
        """)
        premake = textwrap.dedent("""
        include("conanbuildinfo.premake.lua")

        workspace("example")
            conan_basic_setup()

            project("example")
            kind "ConsoleApp"
            language "C++"
            targetdir = "bin/%{cfg.buildcfg}"

            filter "configurations:Debug"
                defines { "DEBUG" }
                symbols "On"

            filter "configurations:Release"
                defines { "NDEBUG" }
                optimize "On"
        """)
        self.client.save({"conanfile.txt": conanfile,
                          "premake5.lua": premake}, clean_first=True)

    def test_generate_basic_setup_release(self):
        self.client.run("install . -s build_type=Release -s arch=x86_64 --build missing")
        self.client.run_command("premake5 vs2017")
        sln_content = load(os.path.join(self.client.current_folder, "example.sln"))
        self.assertIn("Release|x64", sln_content)
        self.assertNotIn("Debug|Win32", sln_content)
        self.assertNotIn("Debug|x64", sln_content)

    def test_generate_basic_setup_debug_32bit(self):
        self.client.run("install . -s build_type=Debug -s arch=x86 --build missing")
        self.client.run_command("premake5 vs2017")
        sln_content = load(os.path.join(self.client.current_folder, "example.sln"))
        self.assertIn("Debug|Win32", sln_content)
        self.assertNotIn("Release|Win32", sln_content)
        self.assertNotIn("Release|x64", sln_content)
