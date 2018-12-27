import os
import textwrap
import unittest

from nose.plugins.attrib import attr

from conans import load
from conans.client.tools import chdir
from conans.test.utils.tools import TestClient


@attr("slow")
@attr("premake")
class PremakeGeneratorTest(unittest.TestCase):

    def setUp(self):
        self.client = TestClient()
        self.client.run("new test/1.0")
        self.client.run("create . danimtb/testing")
        conanfile = textwrap.dedent("""
        [requires]
        test/1.0@danimtb/testing
        
        [generators]
        premake
        """)
        premake = textwrap.dedent("""
        include("conanbuildinfo.lua")

        workspace("example")
            conan_basic_setup()

            project("example")
            kind "ConsoleApp"
            language "C++"
            targetdir = "bin/%{cfg.buildcfg}"

            files{
                "src/**",
            }

            filter "configurations:Debug"
                defines { "DEBUG" }
                symbols "On"

            filter "configurations:Release"
                defines { "NDEBUG" }
                optimize "On"
        """)
        hello_cpp = textwrap.dedent("""
        #include "hello.h"
        
        int main()
        {
            hello();
        }
        """)
        self.client.save({"conanfile.txt": conanfile,
                          "premake5.lua": premake,
                          "hello.cpp": hello_cpp}, clean_first=True)
        self.client.run("install .")

    
    def test_generate_basic_setup(self):
        with chdir(self.client.current_folder):
            self.client.runner("premake5 vs2017")
        print(load(os.path.join(self.client.current_folder, "example.sln")))
        print(self.client.out)
        print(os.listdir(self.client.current_folder))
