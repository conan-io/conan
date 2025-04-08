import textwrap

from conan.test.utils.mocks import ConanFileMock
from conan.test.utils.tools import TestClient
from conan.tools.env.environment import environment_wrap_command
from conan.test.assets.genconanfile import GenConanfile


def assert_vars_file(client, configuration):
    contents = client.load(f"conan_pkg.name-more+_vars_{configuration}_x86_64.premake5.lua")
    assert f'include "conanutils.premake5.lua"' in contents
    assert f't_conandeps = {{}}' in contents
    assert f't_conandeps["{configuration}_x86_64"] = {{}}' in contents
    assert f't_conandeps["{configuration}_x86_64"]["pkg.name-more+"] = {{}}' in contents
    assert f't_conandeps["{configuration}_x86_64"]["pkg.name-more+"]["includedirs"]' in contents
    assert f't_conandeps["{configuration}_x86_64"]["pkg.name-more+"]["libdirs"]' in contents
    assert f't_conandeps["{configuration}_x86_64"]["pkg.name-more+"]["bindirs"]' in contents
    assert f't_conandeps["{configuration}_x86_64"]["pkg.name-more+"]["libs"]' in contents
    assert f't_conandeps["{configuration}_x86_64"]["pkg.name-more+"]["system_libs"]' in contents
    assert f't_conandeps["{configuration}_x86_64"]["pkg.name-more+"]["defines"]' in contents
    assert f't_conandeps["{configuration}_x86_64"]["pkg.name-more+"]["cxxflags"]' in contents
    assert f't_conandeps["{configuration}_x86_64"]["pkg.name-more+"]["cflags"]' in contents
    assert f't_conandeps["{configuration}_x86_64"]["pkg.name-more+"]["sharedlinkflags"]' in contents
    assert f't_conandeps["{configuration}_x86_64"]["pkg.name-more+"]["exelinkflags"]' in contents
    assert f't_conandeps["{configuration}_x86_64"]["pkg.name-more+"]["frameworks"]' in contents
    assert f'if conandeps == nil then conandeps = {{}} end' in contents
    assert f'conan_premake_tmerge(conandeps, t_conandeps)' in contents


def test_premakedeps():
    # Create package
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            name = "pkg.name-more+"
            version = "1.0"

            def package_info(self):
                self.cpp_info.components["libmpdecimal++"].libs = ["libmp++"]
                self.cpp_info.components["mycomp.some-comp+"].libs = ["mylib"]
                self.cpp_info.components["libmpdecimal++"].requires = ["mycomp.some-comp+"]
        """)
    client.save({"conanfile.py": conanfile}, clean_first=True)
    client.run("create . -s arch=x86_64 -s build_type=Debug")
    client.run("create . -s arch=x86_64 -s build_type=Release")

    # Run conan
    client.run("install --require=pkg.name-more+/1.0@ -g PremakeDeps -s arch=x86_64 -s build_type=Debug")
    client.run("install --require=pkg.name-more+/1.0@ -g PremakeDeps -s arch=x86_64 -s build_type=Release")

    # Assert root lua file
    contents = client.load("conandeps.premake5.lua")
    assert 'include "conan_pkg.name-more+.premake5.lua"' in contents
    assert 'function conan_setup_build(conf, pkg)' in contents
    assert 'function conan_setup_link(conf, pkg)' in contents
    assert 'function conan_setup(conf, pkg)' in contents

    # Assert package root file
    contents = client.load("conan_pkg.name-more+.premake5.lua")
    assert 'include "conan_pkg.name-more+_vars_debug_x86_64.premake5.lua"' in contents
    assert 'include "conan_pkg.name-more+_vars_release_x86_64.premake5.lua"' in contents

    # Assert package per configuration files
    assert_vars_file(client, 'debug')
    assert_vars_file(client, 'release')


def test_todo():
    # Create package
    client = TestClient(path_with_spaces=False)
    # client.run("remote add conancenter https://center2.conan.io")

    def run_pkg(msg):
        host_arch = client.get_default_host_profile().settings['arch']
        cmd_release = environment_wrap_command(ConanFileMock(), f"conanrunenv-release-{host_arch}",
                                               client.current_folder, "dep")
        client.run_command(cmd_release)
        assert "{}: Hello World Release!".format(msg) in client.out

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
        workspace "HelloWorld"
           configurations { "Debug", "Release" }

        project "HelloWorld"
           kind "ConsoleApp"
           language "C++"
           targetdir "bin/%{cfg.buildcfg}"

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
        from conan import ConanFile
        from conan.tools.files import copy, get, collect_libs, chdir, save, replace_in_file
        from conan.tools.layout import basic_layout
        from conan.tools.microsoft import MSBuild
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
                premake.build(workspace="HelloWorld")

            def package(self):
                copy(self, "*.h", os.path.join(self.source_folder, "include"), os.path.join(self.package_folder, "include", "pkg"))
                for lib in ("*.lib", "*.a"):
                    copy(self, lib, es.path.join(self.build_folder, "bin"), os.path.join(self.package_folder, "lib"))
        """)

    client.save({"consumer/conanfile.py": conanfile,
                 "consumer/src/hello.cpp": consumer_source,
                 "consumer/src/premake5.lua": premake5,
                 })

    client.run("create dep")
    client.run("create consumer --build=missing")
    build_folder = client.created_layout().build()
    print(build_folder)

    print(client.out)
    client.run("install consumer")
    run_pkg("Hello World")

    print(client.out)

