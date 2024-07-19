import textwrap

from conan.test.utils.tools import TestClient


def test_conditional_build_type():
    # https://github.com/conan-io/conan/issues/15851
    c = TestClient()
    # A header-only library can't be used for testing, it doesn't fail
    c.run("new cmake_lib -d name=pkga -d version=0.1")
    c.run("create . -s build_type=Debug -tf=")

    c.save({}, clean_first=True)
    c.run("new cmake_lib -d name=pkgb -d version=0.1 -d requires=pkga/0.1")
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMakeToolchain, CMake, cmake_layout, CMakeDeps

        class pkgbRecipe(ConanFile):
            name = "pkgb"
            version = "0.1"
            package_type = "static-library"
            settings = "os", "compiler", "build_type", "arch"
            exports_sources = "CMakeLists.txt", "src/*", "include/*"

            def layout(self):
                cmake_layout(self)

            def generate(self):
                deps = CMakeDeps(self)
                deps.generate()
                tc = CMakeToolchain(self)
                if self.settings.build_type == "Debug":
                    tc.cache_variables["USE_PKGA"] = 1
                    tc.preprocessor_definitions["USE_PKGA"] = 1
                tc.generate()

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()

            def package(self):
                cmake = CMake(self)
                cmake.install()

            def package_info(self):
                self.cpp_info.libs = ["pkgb"]

            def requirements(self):
                if self.settings.build_type == "Debug":
                    self.requires("pkga/0.1")
        """)
    cmake = textwrap.dedent("""\
        cmake_minimum_required(VERSION 3.15)
        project(pkgb CXX)

        add_library(pkgb src/pkgb.cpp)
        target_include_directories(pkgb PUBLIC include)

        if(USE_PKGA)
            find_package(pkga CONFIG REQUIRED)
            target_link_libraries(pkgb PRIVATE pkga::pkga)
        endif()

        set_target_properties(pkgb PROPERTIES PUBLIC_HEADER "include/pkgb.h")
        install(TARGETS pkgb)
        """)
    pkgb_cpp = textwrap.dedent(r"""
        #include <iostream>
        #include "pkgb.h"
        #ifdef USE_PKGA
        #include "pkga.h"
        #endif

        void pkgb(){
            #ifdef USE_PKGA
            pkga();
            #endif

            #ifdef NDEBUG
            std::cout << "pkgb/0.1: Hello World Release!\n";
            #else
            std::cout << "pkgb/0.1: Hello World Debug!\n";
            #endif
        }
        """)
    c.save({"conanfile.py": conanfile,
            "CMakeLists.txt": cmake,
            "src/pkgb.cpp": pkgb_cpp})
    c.run("create . -s build_type=Debug -tf=")
    assert "pkga/0.1" in c.out
    c.run("create . -s build_type=Release -tf=")  # without dep to pkga
    assert "pkga" not in c.out

    c.save({}, clean_first=True)
    c.run("new cmake_lib -d name=pkgc -d version=0.1 -d requires=pkgb/0.1")
    c.run("build . -s build_type=Debug")
    c.run("build . -s build_type=Release")
    # This used to crash because "pkga::pkga"
    assert "conanfile.py (pkgc/0.1): Running CMake.build()" in c.out
