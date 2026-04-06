import platform
import textwrap
import pytest

from conan.test.assets.sources import gen_function_c, gen_function_h
from conan.test.utils.tools import TestClient


@pytest.mark.tool("cmake")
def test_cxx_only_project_links_c_library():
    """
    When the consumer enables only CXX (project(myapp CXX)), the generated CMake config
    must not SEND_ERROR for a dependency with C linkage. CXX implies C linkage support,
    so the template adds "C" to the enabled languages check when "CXX" is present.
    """
    c = TestClient()
    # C library package: builds a static C lib, declares languages = "C" so link_languages = ["C"]
    hello_c = gen_function_c(name="hello")
    hello_h = gen_function_h(name="hello")
    hello_cmake = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(hello C)
        add_library(hello STATIC src/hello.c)
        target_include_directories(hello PUBLIC
          $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
          $<INSTALL_INTERFACE:include>)
        install(TARGETS hello
          ARCHIVE DESTINATION lib
          INCLUDES DESTINATION include)
        install(FILES include/hello.h DESTINATION include)
        """)
    hello_conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMake, cmake_layout

        class Clib(ConanFile):
            name = "hello"
            version = "0.1"
            settings = "os", "compiler", "build_type", "arch"
            package_type = "static-library"
            generators = "CMakeToolchain"
            exports_sources = "CMakeLists.txt", "src/*", "include/*"
            languages = "C"

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
                self.cpp_info.libs = ["hello"]
        """)
    c.save({
        "hello/conanfile.py": hello_conanfile,
        "hello/CMakeLists.txt": hello_cmake,
        "hello/src/hello.c": hello_c,
        "hello/include/hello.h": hello_h,
    })
    c.run("create hello")

    # Consumer: project(CXX) only - no C in project(). Links to C library.
    consumer_cmake = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(myapp CXX)

        find_package(hello CONFIG REQUIRED)

        add_executable(app main.cpp)
        target_link_libraries(app PRIVATE hello::hello)
        """)
    main_cpp = textwrap.dedent("""
        extern "C" {
            #include "hello.h"
        }
        int main() {
            hello();
        }
        """)
    consumer_conanfile = textwrap.dedent("""\
        import os
        from conan import ConanFile
        from conan.tools.cmake import CMake, cmake_layout

        class Recipe(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            package_type = "application"
            generators = "CMakeToolchain", "CMakeConfigDeps"
            requires = "hello/0.1"

            def layout(self):
                cmake_layout(self)

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()
                self.run(os.path.join(self.cpp.build.bindir, "app"), env="conanrun")
        """)
    c.save({
        "consumer/conanfile.py": consumer_conanfile,
        "consumer/CMakeLists.txt": consumer_cmake,
        "consumer/main.cpp": main_cpp,
    })
    c.run("build consumer")

    # If the fix were missing, CMake configure would SEND_ERROR: "Target hello::hello has C
    # linkage but C not enabled in project()". So reaching here and running the app proves the fix.
    assert "hello: Release!" in c.out


@pytest.mark.skipif(platform.system() == "Windows", reason="Windows doesn't fail to link")
def test_auto_cppstd(matrix_c_interface_client):
    c = matrix_c_interface_client
    # IMPORTANT: This must be a C and CXX CMake project!!
    consumer = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(myapp C CXX)

        find_package(matrix REQUIRED)

        add_executable(app app.c)
        target_link_libraries(app PRIVATE matrix::matrix)
        """)

    conanfile = textwrap.dedent("""\
        import os
        from conan import ConanFile
        from conan.tools.cmake import CMake, cmake_layout

        class Recipe(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            package_type = "application"
            generators = "CMakeToolchain", "CMakeConfigDeps"
            requires = "matrix/0.1"

            def layout(self):
                cmake_layout(self)

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()
                self.run(os.path.join(self.cpp.build.bindir, "app"), env="conanrun")
        """)
    app = textwrap.dedent("""
        #include "matrix.h"
        int main(){
            matrix();
            return 0;
        }
        """)
    c.save({"conanfile.py": conanfile,
            "CMakeLists.txt": consumer,
            "app.c": app}, clean_first=True)
    c.run(f"build .")
    assert "Hello Matrix!" in c.out
