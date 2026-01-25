import os
import platform
import shutil
import textwrap

import pytest

from conan.internal.api.new.cmake_lib import test_conanfile_v2
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
    c.run(f"create {shared_arg} --build=never")
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
    core_cpp = gen_function_cpp(name="mypkg_core")
    core_h = gen_function_h(name="mypkg_core")
    utils_cpp = gen_function_cpp(name="mypkg_utils")
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
    c.run(f"create {shared_arg} --build=never")
    assert "mypkg_core: Release!" in c.out
    assert "mypkg_utils: Release!" in c.out


@pytest.mark.tool("cmake", "4.2")
@pytest.mark.parametrize("kind", ["static_public", "static_private", "shared_private"])
def test_cps_components_requires(kind):
    if kind == "shared_private" and platform.system() == "Linux":
        pytest.skip("CPS still doesn't support this case")
    c = TestClient()
    conanfile = textwrap.dedent("""\
        from conan import ConanFile
        from conan.tools.cmake import CMakeToolchain, CMake, cmake_layout
        from conan.cps import CPS
        import glob

        class Recipe(ConanFile):
            name = "{name}"
            version = "0.1"
            package_type = "library"

            settings = "os", "compiler", "build_type", "arch"
            options = {{"shared": [True, False], "fPIC": [True, False]}}
            default_options = {{"shared": False, "fPIC": True}}

            exports_sources = "CMakeLists.txt", "src/*", "include/*"
            implements = ["auto_shared_fpic"]
            generators = "CMakeToolchain", "CMakeConfigDeps"

            def requirements(self):
                {requires}
                pass

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
                file_loc = glob.glob("**/{name}.cps", recursive=True)
                cps_data = CPS.load(file_loc[0])
                # Convert CPS to cpp_info with components
                self.cpp_info = cps_data.to_conan()
        """)

    lib_type = "PUBLIC" if "public" in kind else "PRIVATE"
    cmake = textwrap.dedent("""\
        cmake_minimum_required(VERSION 4.2)
        project({name} CXX)

        set(CMAKE_EXPERIMENTAL_EXPORT_PACKAGE_INFO "b80be207-778e-46ba-8080-b23bba22639e")

        {find}
        # First library: core
        add_library({name}_core src/{name}_core.cpp)
        target_include_directories({name}_core PUBLIC
                    $<BUILD_INTERFACE:${{CMAKE_CURRENT_SOURCE_DIR}}/include>
                    $<INSTALL_INTERFACE:include/core>)
        set_target_properties({name}_core PROPERTIES PUBLIC_HEADER "include/{name}_core.h")
        {deps}

        # Second library: utils (independent from core)
        add_library({name}_utils src/{name}_utils.cpp)

        target_include_directories({name}_utils PUBLIC
                    $<BUILD_INTERFACE:${{CMAKE_CURRENT_SOURCE_DIR}}/include>
                    $<INSTALL_INTERFACE:include/utils>)
        set_target_properties({name}_utils PROPERTIES PUBLIC_HEADER "include/{name}_utils.h")

        target_link_libraries({name}_utils {lib_type} {name}_core)

        install(TARGETS {name}_core EXPORT {name}
                PUBLIC_HEADER DESTINATION ${{CMAKE_INSTALL_INCLUDEDIR}}/core)
        install(TARGETS {name}_utils EXPORT {name}
                PUBLIC_HEADER DESTINATION ${{CMAKE_INSTALL_INCLUDEDIR}}/utils)

        install(PACKAGE_INFO {name} EXPORT {name})
        """)

    # Create source files for both libraries
    core_cpp = gen_function_cpp(name="liba_core")
    core_h = gen_function_h(name="liba_core")
    utils_cpp = gen_function_cpp(name="liba_utils", includes=["liba_core"],
                                 calls=["liba_core"])
    if "public" in kind:
        utils_h = gen_function_h(name="liba_utils", includes=["liba_core"])
    else:
        utils_h = gen_function_h(name="liba_utils")

    # Create test_package files for the two components
    test_package_cmake = textwrap.dedent("""\
        cmake_minimum_required(VERSION 3.15)
        project(PackageTest CXX)

        set(CMAKE_EXPERIMENTAL_FIND_CPS_PACKAGES e82e467b-f997-4464-8ace-b00808fff261)

        find_package({name} CONFIG REQUIRED)

        add_executable(example src/example.cpp)
        target_link_libraries(example {name}::{name}_utils)
        """)

    test_package_example = textwrap.dedent("""\
        #include "{name}_utils.h"

        int main() {{
            {name}_utils();
            return 0;
        }}
        """)
    test_conanfile = test_conanfile_v2.replace("{{package_name}}", "")
    test_conanfile = test_conanfile.replace("CMakeDeps", "CMakeConfigDeps")
    # First, try with the standard liba-config.cmake consumption
    c.save({"conanfile.py": conanfile.format(name="liba", requires=""),
            "CMakeLists.txt": cmake.format(name="liba", lib_type=lib_type, deps="", find=""),
            "src/liba_core.cpp": core_cpp,
            "include/liba_core.h": core_h,
            "src/liba_utils.cpp": utils_cpp,
            "include/liba_utils.h": utils_h,
            "test_package/conanfile.py": test_conanfile,
            "test_package/CMakeLists.txt": test_package_cmake.format(name="liba"),
            "test_package/src/example.cpp": test_package_example.format(name="liba")})

    shared_arg = "-o *:shared=True" if "shared" in kind else ""
    c.run(f"create {shared_arg}")
    assert "liba_core: Release!" in c.out
    assert "liba_utils: Release!" in c.out

    test_conanfile_cps = textwrap.dedent("""\
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
                deps.set_property("liba", "cmake_find_mode", "none")
                deps.set_property("libb", "cmake_find_mode", "none")
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
    c.save({"test_package/conanfile.py": test_conanfile_cps})
    c.run(f"create {shared_arg} --build=never")
    assert "liba_core: Release!" in c.out
    assert "liba_utils: Release!" in c.out

    # Now a second level
    core_cpp = gen_function_cpp(name="libb_core", includes=["liba_utils"], calls=["liba_utils"])
    if "public" in kind:
        core_h = gen_function_h(name="libb_core", includes=["liba_utils"])
    else:
        core_h = gen_function_h(name="libb_core")
    utils_cpp = gen_function_cpp(name="libb_utils", includes=["libb_core"],
                                 calls=["libb_core"])
    if "public" in kind:
        utils_h = gen_function_h(name="libb_utils", includes=["libb_core"])
    else:
        utils_h = gen_function_h(name="libb_utils")

    deps = f'target_link_libraries(libb_core {lib_type} liba::liba_utils)'
    find = f'find_package(liba CONFIG REQUIRED)'
    transitive_headers = "public" in kind
    requires = f'self.requires("liba/0.1", transitive_headers={transitive_headers})'
    c.save({"conanfile.py": conanfile.format(name="libb", requires=requires),
            "CMakeLists.txt": cmake.format(name="libb", lib_type=lib_type, deps=deps, find=find),
            "src/libb_core.cpp": core_cpp,
            "include/libb_core.h": core_h,
            "src/libb_utils.cpp": utils_cpp,
            "include/libb_utils.h": utils_h,
            "test_package/conanfile.py": test_conanfile,
            "test_package/CMakeLists.txt": test_package_cmake.format(name="libb"),
            "test_package/src/example.cpp": test_package_example.format(name="libb")},
           clean_first=True)

    c.run(f"create {shared_arg}")
    assert "libb_core: Release!" in c.out
    assert "libb_utils: Release!" in c.out
    assert "liba_core: Release!" in c.out
    assert "liba_utils: Release!" in c.out

    c.save({"test_package/conanfile.py": test_conanfile_cps})
    c.run(f"create {shared_arg} --build=never")
    assert "libb_core: Release!" in c.out
    assert "libb_utils: Release!" in c.out
    assert "liba_core: Release!" in c.out
    assert "liba_utils: Release!" in c.out


@pytest.mark.skip(reason="Just to report to CMake upstream, and CPS feature request")
@pytest.mark.tool("cmake", "4.2")
def test_pure_cmake_shared():
    c = TestClient()

    cmake = textwrap.dedent("""\
        cmake_minimum_required(VERSION 4.2)
        project(myproj CXX)

        set(CMAKE_EXPERIMENTAL_EXPORT_PACKAGE_INFO "b80be207-778e-46ba-8080-b23bba22639e")

        # First library: core
        add_library(mypkg_core src/mypkg_core.cpp)
        target_include_directories(mypkg_core PUBLIC
                    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
                    $<INSTALL_INTERFACE:include/core>)
        set_target_properties(mypkg_core PROPERTIES PUBLIC_HEADER "include/mypkg_core.h")

        # Second library: utils
        add_library(mypkg_utils src/mypkg_utils.cpp)

        target_include_directories(mypkg_utils PUBLIC
                    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
                    $<INSTALL_INTERFACE:include/utils>)
        set_target_properties(mypkg_utils PROPERTIES PUBLIC_HEADER "include/mypkg_utils.h")

        target_link_libraries(mypkg_utils PRIVATE mypkg_core)

        install(TARGETS mypkg_core EXPORT mypkg
                PUBLIC_HEADER DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}/core)
        install(TARGETS mypkg_utils EXPORT mypkg
                PUBLIC_HEADER DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}/utils)

        install(PACKAGE_INFO mypkg EXPORT mypkg)
        """)

    # Create source files for both libraries
    core_cpp = gen_function_cpp(name="mypkg_core")
    core_h = gen_function_h(name="mypkg_core")
    utils_cpp = gen_function_cpp(name="mypkg_utils", includes=["mypkg_core"],
                                 calls=["mypkg_core"])
    utils_h = gen_function_h(name="mypkg_utils")

    # First, try with the standard mypkg-config.cmake consumption
    c.save({"CMakeLists.txt": cmake,
            "src/mypkg_core.cpp": core_cpp,
            "include/mypkg_core.h": core_h,
            "src/mypkg_utils.cpp": utils_cpp,
            "include/mypkg_utils.h": utils_h})

    c.run_command(f"cmake . -DBUILD_SHARED_LIBS=ON")
    print(c.out)
    c.run_command("cmake --build . --config Release")
    print(c.out)
    c.run_command("cmake --install . --config Release --prefix=mypkginstall")
    print(c.out)
    cps = c.load("mypkginstall/cps/mypkg.cps")
    print(cps)
    cps_release = c.load("mypkginstall/cps/mypkg@release.cps")
    print(cps_release)
