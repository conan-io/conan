import os
import platform
import textwrap

import pytest

from conans.client.tools import replace_in_file
from conans.test.assets.cmake import gen_cmakelists
from conans.test.assets.genconanfile import GenConanfile
from conans.test.assets.sources import gen_function_cpp
from conans.test.utils.tools import TestClient


@pytest.fixture
def client():
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conans.tools import save
        import os
        class Pkg(ConanFile):
            settings = "build_type"
            {}
            def package(self):
                save(os.path.join(self.package_folder, "include", "%s.h" % self.name),
                     '#define MYVAR%s "%s"' % (self.name, self.settings.build_type))
        """)

    c.save({"conanfile.py": conanfile.format("")})
    c.run("create . liba/0.1@ -s build_type=Release")
    c.run("create . liba/0.1@ -s build_type=Debug")
    c.save({"conanfile.py": conanfile.format("requires = 'liba/0.1'")})
    c.run("create . libb/0.1@ -s build_type=Release")
    c.run("create . libb/0.1@ -s build_type=Debug")
    return c


@pytest.mark.tool_cmake
def test_transitive_multi(client):
    # TODO: Make a full linking example, with correct header transitivity

    # Save conanfile and example
    conanfile = textwrap.dedent("""
        [requires]
        libb/0.1

        [generators]
        CMakeDeps
        CMakeToolchain
        """)
    example_cpp = gen_function_cpp(name="main", includes=["libb", "liba"],
                                   preprocessor=["MYVARliba", "MYVARlibb"])
    client.save({"conanfile.txt": conanfile,
                 "CMakeLists.txt": gen_cmakelists(appname="example",
                                                  appsources=["example.cpp"], find_package=["libb"]),
                 "example.cpp": example_cpp}, clean_first=True)

    with client.chdir("build"):
        for bt in ("Debug", "Release"):
            client.run("install .. user/channel -s build_type={}".format(bt))

        # Test that we are using find_dependency with the NO_MODULE option
        # to skip finding first possible FindBye somewhere
        assert "find_dependency(${_DEPENDENCY} REQUIRED NO_MODULE)" in client.load("libb-config.cmake")

        if platform.system() == "Windows":
            client.run_command('cmake .. -G "Visual Studio 15 Win64" '
                               '-DCMAKE_TOOLCHAIN_FILE=conan_toolchain.cmake')
            client.run_command('cmake --build . --config Debug')
            client.run_command('cmake --build . --config Release')

            client.run_command('Debug\\example.exe')
            assert "main: Debug!" in client.out
            assert "MYVARliba: Debug" in client.out
            assert "MYVARlibb: Debug" in client.out

            client.run_command('Release\\example.exe')
            assert "main: Release!" in client.out
            assert "MYVARliba: Release" in client.out
            assert "MYVARlibb: Release" in client.out
        else:
            # The TOOLCHAIN IS MESSING WITH THE BUILD TYPE and then ignores the -D so I remove it
            replace_in_file(os.path.join(client.current_folder, "conan_toolchain.cmake"),
                            "CMAKE_BUILD_TYPE", "DONT_MESS_WITH_BUILD_TYPE")
            for bt in ("Debug", "Release"):
                client.run_command('cmake .. -DCMAKE_BUILD_TYPE={} '
                                   '-DCMAKE_TOOLCHAIN_FILE=conan_toolchain.cmake'.format(bt))
                client.run_command('cmake --build . --clean-first')

                client.run_command('./example')
                assert "main: {}!".format(bt) in client.out
                assert "MYVARliba: {}".format(bt) in client.out
                assert "MYVARlibb: {}".format(bt) in client.out


@pytest.mark.tool_cmake
def test_system_libs():
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conans.tools import save
        import os

        class Test(ConanFile):
            name = "Test"
            version = "0.1"
            settings = "build_type"
            def package(self):
                save(os.path.join(self.package_folder, "lib/lib1.lib"), "")
                save(os.path.join(self.package_folder, "lib/liblib1.a"), "")

            def package_info(self):
                self.cpp_info.libs = ["lib1"]
                if self.settings.build_type == "Debug":
                    self.cpp_info.system_libs.append("sys1d")
                else:
                    self.cpp_info.system_libs.append("sys1")
        """)
    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run("create . -s build_type=Release")
    client.run("create . -s build_type=Debug")

    conanfile = textwrap.dedent("""
        [requires]
        Test/0.1

        [generators]
        CMakeDeps
        """)
    cmakelists = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(consumer NONE)
        set(CMAKE_PREFIX_PATH ${CMAKE_BINARY_DIR})
        set(CMAKE_MODULE_PATH ${CMAKE_BINARY_DIR})
        find_package(Test)
        message("System libs release: ${Test_SYSTEM_LIBS_RELEASE}")
        message("Libraries to Link release: ${Test_LIBS_RELEASE}")
        message("System libs debug: ${Test_SYSTEM_LIBS_DEBUG}")
        message("Libraries to Link debug: ${Test_LIBS_DEBUG}")
        get_target_property(tmp Test::Test INTERFACE_LINK_LIBRARIES)
        message("Target libs: ${tmp}")
        """)

    for build_type in ["Release", "Debug"]:
        client.save({"conanfile.txt": conanfile, "CMakeLists.txt": cmakelists}, clean_first=True)
        client.run("install conanfile.txt -s build_type=%s" % build_type)
        client.run_command('cmake . -DCMAKE_BUILD_TYPE={0}'.format(build_type))

        library_name = "sys1d" if build_type == "Debug" else "sys1"
        # FIXME: Note it is CONAN_LIB::Test_lib1_RELEASE, not "lib1" as cmake_find_package
        if build_type == "Release":
            assert "System libs release: %s" % library_name in client.out
            assert "Libraries to Link release: lib1" in client.out
            target_libs = ("$<$<CONFIG:Release>:CONAN_LIB::Test_lib1_RELEASE;sys1;"
                           "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,SHARED_LIBRARY>:>;"
                           "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,MODULE_LIBRARY>:>;"
                           "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,EXECUTABLE>:>>")
        else:
            assert "System libs debug: %s" % library_name in client.out
            assert "Libraries to Link debug: lib1" in client.out
            target_libs = ("$<$<CONFIG:Debug>:CONAN_LIB::Test_lib1_DEBUG;sys1d;"
                           "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,SHARED_LIBRARY>:>;"
                           "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,MODULE_LIBRARY>:>;"
                           "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,EXECUTABLE>:>>")
        assert "Target libs: %s" % target_libs in client.out


@pytest.mark.tool_cmake
def test_do_not_mix_cflags_cxxflags():
    # TODO: Verify with components too
    client = TestClient()
    cpp_info = {"cflags": ["one", "two"], "cxxflags": ["three", "four"]}
    client.save({"conanfile.py": GenConanfile("upstream", "1.0").with_package_info(cpp_info=cpp_info,
                                                                                   env_info={})})
    client.run("create .")

    consumer_conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.cmake import CMake

        class Consumer(ConanFile):
            name = "consumer"
            version = "1.0"
            settings = "os", "compiler", "arch", "build_type"
            exports_sources = "CMakeLists.txt"
            requires = "upstream/1.0"
            generators = "CMakeDeps", "CMakeToolchain"

            def build(self):
                cmake = CMake(self)
                cmake.configure()
        """)
    cmakelists = textwrap.dedent("""
       cmake_minimum_required(VERSION 3.15)
       project(consumer NONE)
       find_package(upstream CONFIG REQUIRED)
       get_target_property(tmp upstream::upstream INTERFACE_COMPILE_OPTIONS)
       message("compile options: ${tmp}")
       message("cflags: ${upstream_COMPILE_OPTIONS_C_RELEASE}")
       message("cxxflags: ${upstream_COMPILE_OPTIONS_CXX_RELEASE}")
       """)
    client.save({"conanfile.py": consumer_conanfile,
                 "CMakeLists.txt": cmakelists}, clean_first=True)
    client.run("create .")
    assert "compile options: $<$<CONFIG:Release>:" \
           "$<$<COMPILE_LANGUAGE:CXX>:three;four>;$<$<COMPILE_LANGUAGE:C>:one;two>>" in client.out
    assert "cflags: one;two" in client.out
    assert "cxxflags: three;four" in client.out
