import platform
import textwrap
import pytest

from conan.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() != "Linux",
                    reason="Linux/gcc required for -rpath/-rpath-link testing")
@pytest.mark.tool("cmake", "3.27")
@pytest.mark.parametrize("use_cmake_config_deps", [True, False])
def test_cmake_sysroot_transitive_rpath(use_cmake_config_deps):
    c = TestClient()

    extra_profile = textwrap.dedent("""
        [conf]
        tools.build:sysroot=/path/to/nowhere
    """)

    # Avoid using any C or C++ standard functionality, so that we can "redirect" the sysroot
    # to an empty or non-existing directory
    foo_h = textwrap.dedent("""
        #pragma once
        int foo(int x, int y);
    """)
    foo_cpp = textwrap.dedent("""
        #include "foo.h"
        int foo(int x, int y) {
            return x + y;
        }
    """)
    foo_test = textwrap.dedent("""
        #include "foo.h"
        int main() { return foo(2, 3) == 5 ? 0 : 1; }
    """)
    bar_h = textwrap.dedent("""
        #pragma once
        int bar(int x, int y);
    """)
    bar_cpp = textwrap.dedent("""
        #include "bar.h"
        #include "foo.h"
        int bar(int x, int y) {
            return foo(x, y) * 2;
        }
    """)
    bar_test = textwrap.dedent("""
        #include "bar.h"
        int main() { return bar(2, 3) == 10 ? 0 : 1; }
    """)

    c.save({"extra_profile": extra_profile})
    extra_conf = "-c tools.cmake.cmakedeps:new=will_break_next" if use_cmake_config_deps else ""
    if not use_cmake_config_deps:
        # CMakeConfigDeps does not fail, so nothing extra is needed
        # this is only needed to cover the case of CMakeDeps
        extra_conf += " -c tools.build:add_rpath_link=True"
    with c.chdir("foo"):
        c.run("new cmake_lib -d name=foo -d version=0.1")
        c.save({"include/foo.h": foo_h,
                "src/foo.cpp": foo_cpp,
                "test_package/src/example.cpp": foo_test})
        c.run(f"create . -o '*:shared=True' -pr=default -pr=../extra_profile {extra_conf}")

    with c.chdir("bar"):
        c.run("new cmake_lib -d name=bar -d version=0.1 -d requires=foo/0.1")
        c.save({"include/bar.h": bar_h,
                "src/bar.cpp": bar_cpp,
                "test_package/src/example.cpp": bar_test})
        # skip test package, which fails with CMakeToolchain+CMakeDeps
        c.run(f"create . -o '*:shared=True' -tf= -pr=default -pr=../extra_profile {extra_conf}")
    with c.chdir("app"):
        c.run("new cmake_exe -d name=app -d version=0.1 -d requires=bar/0.1")
        c.save({"src/main.cpp": bar_test,
                "src/app.cpp": ""})
        c.run(f"create . -o '*:shared=True' -pr=default -pr=../extra_profile {extra_conf}")


@pytest.mark.skipif(platform.system() != "Linux",
                    reason="Linux/gcc required for -rpath/-rpath-link testing")
@pytest.mark.tool("cmake", "3.27")
@pytest.mark.parametrize("use_cmake_config_deps", [True, False])
def test_cmake_transitive_rpath_private_internal(use_cmake_config_deps):
    c = TestClient()

    foo_h = textwrap.dedent("""
        #pragma once
        int foo(int x, int y);
    """)
    foo_cpp = textwrap.dedent("""
        #include "foo.h"
        int foo(int x, int y) {
            return x + y;
        }
    """)
    bar_h = textwrap.dedent("""
        #pragma once
        int bar(int x, int y);
    """)
    bar_cpp = textwrap.dedent("""
        #include "bar.h"
        #include "foo.h"
        int bar(int x, int y) {
            return foo(x, y) * 2;
        }
    """)

    foobar_cmakelists = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(foobar CXX)

        add_library(foo src/foo.cpp)
        target_include_directories(foo PUBLIC include)
        set_target_properties(foo PROPERTIES PUBLIC_HEADER "include/foo.h")

        add_library(bar src/bar.cpp)
        target_include_directories(bar PUBLIC include)
        set_target_properties(bar PROPERTIES PUBLIC_HEADER "include/bar.h")
        target_link_libraries(bar PRIVATE foo)

        install(TARGETS foo bar)
    """)

    cmake_deps_gen = "CMakeConfigDeps" if use_cmake_config_deps else "CMakeDeps"
    foobar_conanfile = textwrap.dedent(f"""
        from conan import ConanFile
        from conan.tools.cmake import CMake, cmake_layout


        class foobarRecipe(ConanFile):
            name = "foobar"
            version = "1.0"
            package_type = "library"
            settings = "os", "compiler", "build_type", "arch"
            options = {{"shared": [True, False]}}
            default_options = {{"shared": True}}

            exports_sources = "CMakeLists.txt", "src/*", "include/*"

            generators = "{cmake_deps_gen}", "CMakeToolchain"

            def layout(self):
                cmake_layout(self)

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()

            def package(self):
                cmake = CMake(self)
                cmake.install()

            def package_info(self):
                self.cpp_info.components["foo"].libs = ["foo"]
                self.cpp_info.components["bar"].libs = ["bar"]
                self.cpp_info.components["bar"].requires = ["foo"]
    """)

    consumer_conanfile = textwrap.dedent(f"""
            from conan import ConanFile
            from conan.tools.cmake import CMake, cmake_layout

            class consumerRecipe(ConanFile):
                name = "consumer"
                version = "1.0"
                package_type = "library"
                settings = "os", "compiler", "build_type", "arch"
                options = {{"shared": [True, False]}}
                default_options = {{"shared": True}}
                generators = "{cmake_deps_gen}", "CMakeToolchain"
                exports_sources = "CMakeLists.txt", "src/*", "include/*"

                def layout(self):
                    cmake_layout(self)

                def requirements(self):
                    self.requires("foobar/1.0")

                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
                    cmake.build()

                def package(self):
                    cmake = CMake(self)
                    cmake.install()

                def package_info(self):
                    self.cpp_info.libs = ["consumer"]
    """)

    consumer_cmakelists = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(consumer CXX)

        find_package(foobar CONFIG REQUIRED)

        add_library(consumer src/consumer.cpp)
        target_include_directories(consumer PUBLIC include)
        target_link_libraries(consumer PRIVATE ${foobar_LIBRARIES}) # foobar_LIBRARIES is foobar::foobar
        set_target_properties(consumer PROPERTIES PUBLIC_HEADER "include/consumer.h")
        install(TARGETS consumer)

        add_executable(my_app src/my_app.cpp)
        target_link_libraries(my_app PRIVATE consumer)
    """)

    consumer_cpp = textwrap.dedent("""
    #include "consumer.h"
    #include "bar.h"
    int consumer(int x, int y) {return bar(x, y) * 2;}
    """)

    consumer_h = textwrap.dedent("""
    #pragma once
    int consumer(int x, int y);
    """)

    my_app_cpp = textwrap.dedent("""
    #include "consumer.h"
    int main() { return consumer(2, 3) == 20 ? 0 : 1; }
    """)

    extra_conf = "-c tools.build:add_rpath_link=True"  # removing this should break the test

    with c.chdir("foobar"):
        c.save({"include/foo.h": foo_h,
                "include/bar.h": bar_h,
                "src/foo.cpp": foo_cpp,
                "src/bar.cpp": bar_cpp,
                "CMakeLists.txt": foobar_cmakelists,
                "conanfile.py": foobar_conanfile})
        c.run(f"create . {extra_conf} ")

    with c.chdir("consumer"):
        c.save({"src/consumer.cpp": consumer_cpp,
                "include/consumer.h": consumer_h,
                "src/my_app.cpp": my_app_cpp,
                "CMakeLists.txt": consumer_cmakelists,
                "conanfile.py": consumer_conanfile})
        c.run(f"create . {extra_conf}")
