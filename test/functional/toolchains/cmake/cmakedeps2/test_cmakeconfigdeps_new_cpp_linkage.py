import platform
import textwrap
import pytest


new_value = "will_break_next"


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
            generators = "CMakeToolchain", "CMakeDeps"
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
    c.run(f"build . -c tools.cmake.cmakedeps:new={new_value}")
    assert "Hello Matrix!" in c.out
