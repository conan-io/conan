import textwrap

from conan.test.utils.tools import TestClient
import os


def test_premake_args():
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.premake import Premake, PremakeToolchain

        class Pkg(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            def run(self, cmd, *args, **kwargs):
                self.output.info(f"Running {cmd}!!")
            def generate(self):
                toolchain = PremakeToolchain(self)
                toolchain.generate()
            def build(self):
                premake = Premake(self)
                premake.luafile = "myproject.lua"
                premake.arguments = {"myarg": "myvalue"}
                premake.configure()
                """)
    c.save({"conanfile.py": conanfile})
    c.run("build . -s compiler=msvc -s compiler.version=193 -s compiler.runtime=dynamic")
    assert "conanfile.py: Running premake5" in c.out
    assert "conanfile.premake5.lua vs2022 --myarg=myvalue!!" in c.out


def test_premake_full_compilation():
    client = TestClient(path_with_spaces=False)
    client.run("new cmake_lib -d name=dep -d version=1.0 -o dep")

    consumer_source = textwrap.dedent("""
        #include <iostream>
        #include "dep.h"

        int main(void) {
           dep();
           std::cout << "Hello World" << std::endl;
           return 0;
        }
    """)

    premake5 = textwrap.dedent("""
        workspace "Project"
           language "C++"
           configurations { "Debug", "Release" }

        project "app"
           kind "ConsoleApp"
           files { "**.h", "**.cpp" }
           filter "configurations:Debug"
              defines { "DEBUG" }
              symbols "On"
           filter "configurations:Release"
              defines { "NDEBUG" }
              optimize "On"
    """)


    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.layout import basic_layout
        from conan.tools.premake import Premake, PremakeDeps, PremakeToolchain
        import os

        class Pkg(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            name = "pkg"
            version = "1.0"
            exports_sources = '*'

            def layout(self):
                basic_layout(self, src_folder="src")

            def requirements(self):
                self.requires("dep/1.0")

            def generate(self):
                deps = PremakeDeps(self)
                deps.generate()
                tc = PremakeToolchain(self)
                tc.generate()

            def build(self):
                premake = Premake(self)
                premake.configure()
                premake.build(workspace="Project", targets=["app"])
        """)

    client.save({"consumer/conanfile.py": conanfile,
                 "consumer/src/hello.cpp": consumer_source,
                 "consumer/src/premake5.lua": premake5,
                 })

    client.run("create dep")
    client.run("create consumer")
    bin_folder = os.path.join(client.created_layout().build(), "build-release", "bin")
    exe_path = os.path.join(bin_folder, "app")
    assert os.path.exists(exe_path)
    client.run_command(exe_path)
    assert "dep/1.0: Hello World Release!" in client.out
