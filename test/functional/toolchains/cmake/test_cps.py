import os
import shutil
import textwrap

import pytest

from conan.test.assets.sources import gen_function_h, gen_function_cpp
from conan.test.utils.tools import TestClient


@pytest.mark.tool("cmake", "4.2")
@pytest.mark.parametrize("shared", [False, True])
def test_cps(shared):
    c = TestClient()
    c.run("new cmake_lib")
    conanfile = textwrap.dedent("""\
        from conan import ConanFile
        from conan.tools.cmake import CMakeToolchain, CMake, cmake_layout
        from conan.cps import CPS
        import glob

        class mypkgRecipe(ConanFile):
            name = "mypkg"
            version = "0.1"
            package_type = "library"

            settings = "os", "compiler", "build_type", "arch"
            options = {"shared": [True, False], "fPIC": [True, False]}
            default_options = {"shared": False, "fPIC": True}

            exports_sources = "CMakeLists.txt", "src/*", "include/*"
            implements = ["auto_shared_fpic"]
            generators = "CMakeToolchain"

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
                file_loc = glob.glob("**/mypkg.cps", recursive=True)
                self.cpp_info = CPS.load(file_loc[0]).to_conan()
        """)

    cmake = textwrap.dedent("""\
        cmake_minimum_required(VERSION 4.2)
        project(mypkg CXX)

        set(CMAKE_EXPERIMENTAL_EXPORT_PACKAGE_INFO "b80be207-778e-46ba-8080-b23bba22639e")

        add_library(mypkg src/mypkg.cpp)
        target_include_directories(mypkg PUBLIC
                    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
                    $<INSTALL_INTERFACE:include>)

        set_target_properties(mypkg PROPERTIES PUBLIC_HEADER "include/mypkg.h")
        install(TARGETS mypkg EXPORT mypkg)

        install(PACKAGE_INFO mypkg EXPORT mypkg)
        """)

    # First, try with the standard mypkg-config.cmake consumption
    c.save({"conanfile.py": conanfile,
            "CMakeLists.txt": cmake})

    shared_arg = "-o &:shared=True" if shared else ""
    c.run(f"create {shared_arg}")
    assert "mypkg/0.1: Hello World Release!" in c.out

    # Lets consume directly with CPS
    test_cmake = textwrap.dedent("""\
        cmake_minimum_required(VERSION 4.2)
        project(PackageTest CXX)

        set(CMAKE_EXPERIMENTAL_FIND_CPS_PACKAGES e82e467b-f997-4464-8ace-b00808fff261)

        find_package(mypkg CONFIG REQUIRED)

        add_executable(example src/example.cpp)
        target_link_libraries(example mypkg::mypkg)
        """)
    test_conanfile = textwrap.dedent("""\
        import os

        from conan import ConanFile
        from conan.tools.cmake import CMake, cmake_layout, CMakeToolchain, CMakeConfigDeps
        from conan.tools.build import can_run


        class TestConan(ConanFile):
            settings = "os", "compiler", "build_type", "arch"

            def requirements(self):
                self.requires(self.tested_reference_str)

            def generate(self):
                deps = CMakeConfigDeps(self)
                deps.set_property("mypkg", "cmake_find_mode", "none")
                deps.generate()
                tc = CMakeToolchain(self)
                tc.generate()

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()

            def layout(self):
                cmake_layout(self)

            def test(self):
                if can_run(self):
                    cmd = os.path.join(self.cpp.build.bindir, "example")
                    self.run(cmd, env="conanrun")
            """)
    shutil.rmtree(os.path.join(c.current_folder, "test_package", "build"))
    c.save({"test_package/conanfile.py": test_conanfile,
            "test_package/CMakeLists.txt": test_cmake})
    c.run(f"create {shared_arg} --build=never -c tools.cmake.cmakedeps:new=will_break_next")
    assert "mypkg/0.1: Hello World Release!" in c.out


@pytest.mark.tool("cmake", "4.2")
@pytest.mark.parametrize("shared", [False, True])
def test_cps_components(shared):
    c = TestClient()
    c.run("new cmake_lib")
    conanfile = textwrap.dedent("""\
        from conan import ConanFile
        from conan.tools.cmake import CMakeToolchain, CMake, cmake_layout
        from conan.cps import CPS
        import glob

        class mypkgRecipe(ConanFile):
            name = "mypkg"
            version = "0.1"
            package_type = "library"

            settings = "os", "compiler", "build_type", "arch"
            options = {"shared": [True, False], "fPIC": [True, False]}
            default_options = {"shared": False, "fPIC": True}

            exports_sources = "CMakeLists.txt", "src/*", "include/*"
            implements = ["auto_shared_fpic"]
            generators = "CMakeToolchain"

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
                file_loc = glob.glob("**/mypkg.cps", recursive=True)
                cps_data = CPS.load(file_loc[0])
                # Convert CPS to cpp_info with components
                self.cpp_info = cps_data.to_conan()
        """)

    cmake = textwrap.dedent("""\
        cmake_minimum_required(VERSION 4.2)
        project(mypkg CXX)

        set(CMAKE_EXPERIMENTAL_EXPORT_PACKAGE_INFO "b80be207-778e-46ba-8080-b23bba22639e")

        # First library: core
        add_library(mypkg_core src/mypkg_core.cpp)
        target_include_directories(mypkg_core PUBLIC
                    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
                    $<INSTALL_INTERFACE:include>)
        set_target_properties(mypkg_core PROPERTIES PUBLIC_HEADER "include/mypkg_core.h")

        # Second library: utils (independent from core)
        add_library(mypkg_utils src/mypkg_utils.cpp)
        target_include_directories(mypkg_utils PUBLIC
                    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
                    $<INSTALL_INTERFACE:include>)
        set_target_properties(mypkg_utils PROPERTIES PUBLIC_HEADER "include/mypkg_utils.h")

        install(TARGETS mypkg_core mypkg_utils EXPORT mypkg)

        install(PACKAGE_INFO mypkg EXPORT mypkg)
        """)

    # Create source files for both libraries
    core_cpp = gen_function_cpp(name="mypkg_core", includes=["mypkg_core"])
    core_h = gen_function_h(name="mypkg_core")
    utils_cpp = gen_function_cpp(name="mypkg_utils", includes=["mypkg_utils"])
    utils_h = gen_function_h(name="mypkg_utils")

    # Create test_package files for the two components
    test_package_cmake = textwrap.dedent("""\
        cmake_minimum_required(VERSION 3.15)
        project(PackageTest CXX)

        set(CMAKE_EXPERIMENTAL_FIND_CPS_PACKAGES e82e467b-f997-4464-8ace-b00808fff261)

        find_package(mypkg CONFIG REQUIRED)

        add_executable(example src/example.cpp)
        target_link_libraries(example mypkg::mypkg_core mypkg::mypkg_utils)
        """)

    test_package_example = textwrap.dedent("""\
        #include "mypkg_core.h"
        #include "mypkg_utils.h"

        int main() {
            mypkg_core();
            mypkg_utils();
            return 0;
        }
        """)

    # First, try with the standard mypkg-config.cmake consumption
    c.save({"conanfile.py": conanfile,
            "CMakeLists.txt": cmake,
            "src/mypkg_core.cpp": core_cpp,
            "include/mypkg_core.h": core_h,
            "src/mypkg_utils.cpp": utils_cpp,
            "include/mypkg_utils.h": utils_h,
            "test_package/CMakeLists.txt": test_package_cmake,
            "test_package/src/example.cpp": test_package_example})

    shared_arg = "-o &:shared=True" if shared else ""
    c.run(f"create {shared_arg}")
    assert "mypkg_core: Release!" in c.out
    assert "mypkg_utils: Release!" in c.out

    test_conanfile = textwrap.dedent("""\
        import os

        from conan import ConanFile
        from conan.tools.cmake import CMake, cmake_layout, CMakeToolchain, CMakeConfigDeps
        from conan.tools.build import can_run


        class TestConan(ConanFile):
            settings = "os", "compiler", "build_type", "arch"

            def requirements(self):
                self.requires(self.tested_reference_str)

            def generate(self):
                deps = CMakeConfigDeps(self)
                deps.set_property("mypkg", "cmake_find_mode", "none")
                deps.generate()
                tc = CMakeToolchain(self)
                tc.generate()

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()

            def layout(self):
                cmake_layout(self)

            def test(self):
                if can_run(self):
                    cmd = os.path.join(self.cpp.build.bindir, "example")
                    self.run(cmd, env="conanrun")
            """)
    shutil.rmtree(os.path.join(c.current_folder, "test_package", "build"))
    c.save({"test_package/conanfile.py": test_conanfile})
    c.run(f"create {shared_arg} --build=never -c tools.cmake.cmakedeps:new=will_break_next")
    assert "mypkg_core: Release!" in c.out
    assert "mypkg_utils: Release!" in c.out
