import os
import platform
import textwrap

from conan.test.assets.premake import gen_premake5
from conan.test.utils.mocks import ConanFileMock
from conan.tools.files.files import replace_in_file, rmdir
import pytest

from conan.test.utils.tools import TestClient
from conan.test.assets.sources import gen_function_cpp

@pytest.mark.skipif(platform.machine() != "x86_64", reason="Premake Legacy generator only supports x86_64 machines")
@pytest.mark.tool("premake")
def test_premake_legacy(matrix_client):
    c = matrix_client
    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.premake import Premake
        from conan.tools.microsoft import MSBuild
        class Pkg(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            requires = "matrix/1.0"
            generators = "PremakeDeps", "VCVars"
            def build(self):
                p = Premake(self)
                p.configure()
                build_type = str(self.settings.build_type)
                if self.settings.os == "Windows":
                    msbuild = MSBuild(self)
                    msbuild.build("HelloWorld.sln")
                else:
                    self.run(f"make config={build_type.lower()}_x86_64")
                p = os.path.join(self.build_folder, "bin", build_type, "HelloWorld")
                self.run(f'"{p}"')
        """)
    premake = textwrap.dedent("""
        -- premake5.lua

        include('conandeps.premake5.lua')

        workspace "HelloWorld"
           conan_setup()
           configurations { "Debug", "Release" }
           platforms { "x86_64" }

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

           filter "platforms:x86_64"
              architecture "x86_64"
          """)
    c.save({"conanfile.py": conanfile,
            "premake5.lua": premake,
            "main.cpp": gen_function_cpp(name="main", includes=["matrix"], calls=["matrix"])})
    c.run("build .")
    assert "main: Release!" in c.out
    assert "matrix/1.0: Hello World Release!" in c.out
    if platform.system() == "Windows":
        assert "main _M_X64 defined" in c.out
    else:
        assert "main __x86_64__ defined" in c.out
    c.run("build . -s build_type=Debug --build=missing")
    assert "main: Debug!" in c.out
    assert "matrix/1.0: Hello World Debug!" in c.out



@pytest.mark.tool("premake")
def test_premake_new_generator():
    c = TestClient()
    c.run("new premake_lib -d name=lib -d version=0.1 -o lib")
    c.run("create lib")
    c.run("new premake_exe -d name=example -d requires=lib/0.1 -d version=1.0 -o exe")
    c.run("create exe")

    assert "example/1.0 (test package): RUN: example" in c.out
    assert "lib/0.1: Hello World Release!" in c.out
    assert "example/1.0: Hello World Release!" in c.out


@pytest.mark.tool("premake")
def test_premake_shared_lib():
    c = TestClient()
    c.run("new premake_lib -d name=lib -d version=0.1 -o lib")
    c.run("create lib -o '&:shared=True'")
    assert "lib/0.1: package(): Packaged 1 '.so' file: liblib.so" in c.out
    assert "lib/0.1: package(): Packaged 1 '.a' file: liblib.a" not in c.out


@pytest.mark.tool("premake")
@pytest.mark.parametrize("transitive_libs", [True, False])
def test_premake_components(transitive_libs):
    c = TestClient()
    c.run("new premake_lib -d name=liba -d version=1.0 -o liba")

    libb_premake = gen_premake5(
        workspace="Libb",
        includedirs=[".", "libb1", "libb2"],
        projects=[
            {"name": "libb1", "files": ["libb1/*.h", "libb1/*.cpp"], "kind": "StaticLib"},
            {"name": "libb2", "files": ["libb2/*.h", "libb2/*.cpp"], "kind": "StaticLib", "links": ["libb1"]}
        ]
    )
    libb_conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import copy
        from conan.tools.layout import basic_layout
        from conan.tools.premake import Premake


        class libbRecipe(ConanFile):
            name = "libb"
            version = "1.0"
            package_type = "static-library"
            settings = "os", "compiler", "build_type", "arch"
            exports_sources = "premake5.lua", "libb1/*", "libb2/*"
            generators= "PremakeDeps", "PremakeToolchain"

            def layout(self):
                basic_layout(self)

            def requirements(self):
                self.requires("liba/1.0", transitive_libs=%s)

            def build(self):
                premake = Premake(self)
                premake.configure()
                premake.build(workspace="Libb")

            def package(self):
                for lib in ("libb1", "libb2"):
                    copy(self, "*.h", os.path.join(self.source_folder, lib), os.path.join(self.package_folder, "include", lib))

                for pattern in ("*.lib", "*.a", "*.so*", "*.dylib"):
                    copy(self, pattern, os.path.join(self.build_folder, "bin"), os.path.join(self.package_folder, "lib"))
                copy(self, "*.dll", os.path.join(self.build_folder, "bin"), os.path.join(self.package_folder, "bin"))

            def package_info(self):
                self.cpp_info.components["libb1"].libs = ["libb1"]
                self.cpp_info.components["libb1"].requires = ["liba::liba"]

                self.cpp_info.components["libb2"].libs = ["libb2"]
                self.cpp_info.components["libb2"].requires = ["libb1"]
    """)

    libb_h = textwrap.dedent("""
        #pragma once
        #include <string>
        void libb%s();
    """)

    libb_cpp = textwrap.dedent("""
        #include <iostream>
        #include "libb%s.h"
        #include "liba.h"
        void libb%s(){
            liba();
            std::cout << "libb%s/1.0" << std::endl;
        }
    """)

    c.save(
        {
            "libb/premake5.lua": libb_premake,
            "libb/conanfile.py": libb_conanfile % transitive_libs,
            "libb/libb1/libb1.h": libb_h % "1",
            "libb/libb1/libb1.cpp": libb_cpp % ("1", "1", "1"),
            "libb/libb2/libb2.h": libb_h % "2",
            "libb/libb2/libb2.cpp": libb_cpp % ("2", "2", "2"),
        }
    )
    # Create a consumer application which depends on libb
    c.run("new premake_exe -d name=consumer -d version=1.0 -o consumer -d requires=libb/1.0")
    # Adapt includes and usage of libb in the consumer application
    replace_in_file(ConanFileMock(), os.path.join(c.current_folder, "consumer", "src", "consumer.cpp"),
                    '#include "libb.h"', '#include "libb1/libb1.h"\n#include "libb2/libb2.h"')
    replace_in_file(ConanFileMock(), os.path.join(c.current_folder, "consumer", "src", "consumer.cpp"),
                    'libb()', 'libb1();libb2()')

    c.run("create liba")
    c.run("create libb")
    # If transitive_libs is false, consumer will not compile because it will not find liba
    c.run("build consumer", assert_error=not transitive_libs)


@pytest.mark.tool("premake")
def test_transitive_headers_not_public(transitive_libraries):
    c = transitive_libraries

    main = gen_function_cpp(name="main", includes=["engine"], calls=["engine"])
    premake5 = gen_premake5(
        workspace="Consumer",
        projects=[
            {"name": "consumer", "files": ["src/main.cpp"], "kind": "ConsoleApp"}
        ],
    )

    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.layout import basic_layout
        from conan.tools.premake import Premake

        class ConsumerRecipe(ConanFile):
            name = "consumer"
            version = "1.0"
            package_type = "application"
            settings = "os", "compiler", "build_type", "arch"
            exports_sources = "*"
            generators= "PremakeDeps", "PremakeToolchain"

            def layout(self):
                basic_layout(self)

            def requirements(self):
                self.requires("engine/1.0")

            def build(self):
                premake = Premake(self)
                premake.configure()
                premake.build(workspace="Consumer")
    """)

    c.save({"src/main.cpp": main,
            "premake5.lua": premake5,
            "conanfile.py": conanfile
            })
    # Test it builds successfully
    c.run("build .")

    # Test including a transitive header: it should fail as engine does not require matrix with
    # transitive_headers enabled
    main = gen_function_cpp(name="main", includes=["engine", "matrix"], calls=["engine"])
    c.save({"src/main.cpp": main})
    rmdir(ConanFileMock(), os.path.join(c.current_folder, "build-release"))
    c.run("build .", assert_error=True)
    # Error should be about not finding matrix

