import re
import textwrap

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient

new_value = "will_break_next"


def test_cmakedeps_direct_deps_paths():
    c = TestClient()
    conanfile = textwrap.dedent("""
        import os
        from conan.tools.files import copy
        from conan import ConanFile
        class TestConan(ConanFile):
            name = "lib"
            version = "1.0"
            def package_info(self):
                self.cpp_info.includedirs = ["myincludes"]
                self.cpp_info.libdirs = ["mylib"]
                self.cpp_info.frameworkdirs = ["myframework"]
    """)
    c.save({"conanfile.py": conanfile})
    c.run("create .")
    conanfile = textwrap.dedent(f"""
        from conan import ConanFile
        from conan.tools.cmake import CMake
        class PkgConan(ConanFile):
            requires = "lib/1.0"
            settings = "os", "arch", "compiler", "build_type"
            generators = "CMakeDeps"
    """)
    c.save({"conanfile.py": conanfile}, clean_first=True)
    c.run(f"install . -c tools.cmake.cmakedeps:new={new_value}")
    cmake_paths = c.load("conan_cmakedeps_paths.cmake")
    assert re.search(r"list\(PREPEND CMAKE_PROGRAM_PATH \".*/bin\"", cmake_paths)  # default
    assert re.search(r"list\(PREPEND CMAKE_LIBRARY_PATH \".*/mylib\"", cmake_paths)
    assert re.search(r"list\(PREPEND CMAKE_INCLUDE_PATH \".*/myincludes\"", cmake_paths)
    assert re.search(r"list\(PREPEND CMAKE_FRAMEWORK_PATH \".*/myframework\"", cmake_paths)


def test_cmakedeps_transitive_paths():
    c = TestClient()
    conanfile = textwrap.dedent("""
        import os
        from conan.tools.files import copy
        from conan import ConanFile
        class TestConan(ConanFile):
            name = "liba"
            version = "1.0"
            def package_info(self):
                self.cpp_info.includedirs = ["includea"]
                self.cpp_info.libdirs = ["liba"]
                self.cpp_info.bindirs = ["bina"]
    """)
    c.save({"conanfile.py": conanfile})
    c.run("create .")
    conanfile = textwrap.dedent("""
        import os
        from conan.tools.files import copy
        from conan import ConanFile
        class TestConan(ConanFile):
            name = "libb"
            version = "1.0"
            requires = "liba/1.0"
            def package_info(self):
                self.cpp_info.includedirs = ["includeb"]
                self.cpp_info.libdirs = ["libb"]
                self.cpp_info.bindirs = ["binb"]
    """)
    c.save({"conanfile.py": conanfile})
    c.run("create .")
    conanfile = textwrap.dedent(f"""
        from conan import ConanFile
        class PkgConan(ConanFile):
            requires = "libb/1.0"
            settings = "os", "arch", "compiler", "build_type"
            generators = "CMakeDeps"
    """)
    c.save({"conanfile.py": conanfile}, clean_first=True)
    c.run(f"install . -c tools.cmake.cmakedeps:new={new_value}")
    cmake_paths = c.load("conan_cmakedeps_paths.cmake")
    assert re.search(r"list\(PREPEND CMAKE_PROGRAM_PATH \".*/libb.*/p/binb\"\)", cmake_paths)
    assert not re.search(r"list\(PREPEND CMAKE_PROGRAM_PATH /bina\"", cmake_paths)
    assert re.search(r"list\(PREPEND CMAKE_LIBRARY_PATH \".*/libb.*/p/libb\" \".*/liba.*/p/liba\"\)", cmake_paths)
    assert re.search(r"list\(PREPEND CMAKE_INCLUDE_PATH \".*/libb.*/p/includeb\" \".*/liba.*/p/includea\"\)", cmake_paths)


def test_cmakedeps_deployer_relative_paths():
    c = TestClient()
    conanfile = textwrap.dedent("""
        import os
        from conan.tools.files import copy
        from conan import ConanFile
        class TestConan(ConanFile):
            name = "liba"
            version = "1.0"

            def package_info(self):
                self.cpp_info.includedirs = ["includea"]
                self.cpp_info.libdirs = ["bina"]
                self.cpp_info.bindirs = ["bina"]
                crypto_module = os.path.join("share", "cmake", "crypto.cmake")
                self.cpp_info.set_property("cmake_build_modules", [crypto_module])
    """)
    c.save({"conanfile.py": conanfile})
    c.run("create .")

    conanfile_cmake = textwrap.dedent("""
        import os
        from conan.tools.files import save
        from conan import ConanFile
        class TestConan(ConanFile):
            name = "libb"
            version = "1.0"

            def package(self):
                save(self, os.path.join(self.package_folder, "libb-config.cmake"), "")
            def package_info(self):
                self.cpp_info.set_property("cmake_find_mode", "none")
        """)

    c.save({"conanfile.py": conanfile_cmake})
    c.run("create .")
    conanfile = textwrap.dedent(f"""
        from conan import ConanFile
        from conan.tools.cmake import CMake
        class PkgConan(ConanFile):
            requires = "liba/1.0", "libb/1.0"
            settings = "os", "arch", "compiler", "build_type"
            generators = "CMakeDeps"
    """)
    c.save({"conanfile.py": conanfile}, clean_first=True)

    # Now with a deployment
    c.run(f"install . -c tools.cmake.cmakedeps:new={new_value} --deployer=full_deploy")
    cmake_paths = c.load("conan_cmakedeps_paths.cmake")
    assert 'set(libb_DIR "${CMAKE_CURRENT_LIST_DIR}/full_deploy/host/libb/1.0")' in cmake_paths
    assert ('set(CONAN_RUNTIME_LIB_DIRS "$<$<CONFIG:Release>:${CMAKE_CURRENT_LIST_DIR}'
            '/full_deploy/host/liba/1.0/bina>"') in cmake_paths
    liba_config = c.load("liba-config.cmake")
    assert ('include("${CMAKE_CURRENT_LIST_DIR}/full_deploy/'
            'host/liba/1.0/share/cmake/crypto.cmake")') in liba_config
    liba_targets = c.load("liba-Targets-release.cmake")
    assert ('set(liba_PACKAGE_FOLDER_RELEASE "${CMAKE_CURRENT_LIST_DIR}/full_deploy/'
            'host/liba/1.0")') in liba_targets
    assert ('set(liba_INCLUDE_DIRS "${CMAKE_CURRENT_LIST_DIR}/full_deploy/'
            'host/liba/1.0/includea" )') in liba_targets

def test_cmakeconfigdeps_recipe():
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conan.tools.cmake import CMakeConfigDeps
        from conan import ConanFile
        class TestConan(ConanFile):
            settings = "build_type"
            requires = "dep/0.1"
            def generate(self):
                deps = CMakeConfigDeps(self)
                deps.generate()
    """)
    c.save({"dep/conanfile.py": GenConanfile("dep", "0.1"),
            "app/conanfile.py": conanfile})
    c.run("create dep")
    c.run("install app", assert_error=True)
    assert "CMakeConfigDeps is being used in conanfile, but the conf " \
           "'tools.cmake.cmakedeps:new' is not enabled" in c.out
    c.run("install app -c tools.cmake.cmakedeps:new=will_break_next")
    # will not fail, still warn
    assert "WARN: Using the new CMakeConfigDeps generator" in c.out
    # The only-recipe also not fails
    c.run("install app -c tools.cmake.cmakedeps:new=recipe_will_break")
    # will not fail
    assert "WARN: Using the new CMakeConfigDeps generator" in c.out

    # attribute generator
    conanfile = textwrap.dedent("""
        from conan.tools.cmake import CMakeConfigDeps
        from conan import ConanFile
        class TestConan(ConanFile):
            settings = "build_type"
            requires = "dep/0.1"
            generators = "CMakeConfigDeps"
        """)
    c.save({"app/conanfile.py": conanfile}, clean_first=True)
    c.run("install app", assert_error=True)
    assert "CMakeConfigDeps is being used in conanfile, but the conf " \
           "'tools.cmake.cmakedeps:new' is not enabled" in c.out
    c.run("install app -c tools.cmake.cmakedeps:new=will_break_next")
    assert "WARN: Using the new CMakeConfigDeps generator" in c.out
    c.run("install app -c tools.cmake.cmakedeps:new=recipe_will_break")
    assert "WARN: Using the new CMakeConfigDeps generator" in c.out

    # conanfile.txt
    conanfile = textwrap.dedent("""
        [requires]
        dep/0.1
        [generators]
        CMakeConfigDeps
        """)
    c.save({"app/conanfile.txt": conanfile}, clean_first=True)
    c.run("install app", assert_error=True)
    assert "CMakeConfigDeps is being used in conanfile, but the conf " \
           "'tools.cmake.cmakedeps:new' is not enabled" in c.out
    c.run("install app -c tools.cmake.cmakedeps:new=will_break_next")
    assert "WARN: Using the new CMakeConfigDeps generator" in c.out
    c.run("install app -c tools.cmake.cmakedeps:new=recipe_will_break")
    assert "WARN: Using the new CMakeConfigDeps generator" in c.out


def test_system_wrappers():
    c = TestClient()
    conanfile = textwrap.dedent("""
        import os
        from conan.tools.files import copy
        from conan import ConanFile
        class TestConan(ConanFile):
            name = "lib"
            version = "system"
            package_type = "shared-library"

            def package_info(self):
                self.cpp_info.includedirs = []
                self.cpp_info.libdirs = []
                self.cpp_info.system_libs = ["my_system_cool_lib"]
    """)
    c.save({"conanfile.py": conanfile})
    c.run("create .")

    c.run(f"install --requires=lib/system -g CMakeConfigDeps "
          f"-c tools.cmake.cmakedeps:new={new_value}")
    cmake = c.load("lib-Targets-release.cmake")
    assert "add_library(lib::lib INTERFACE IMPORTED)" in cmake
    assert "target_link_libraries(lib::lib INTERFACE my_system_cool_lib)" in cmake


def test_autolink_pragma():
    """https://github.com/conan-io/conan/issues/10837"""
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            def package_info(self):
                self.cpp_info.set_property("cmake_set_interface_link_directories", True)
        """)
    c.save({"conanfile.py": conanfile,
            "test_package/conanfile.py": GenConanfile().with_test("pass")
                                                       .with_settings("build_type")
                                                       .with_generator("CMakeDeps")})
    c.run("create . --name=pkg --version=0.1")
    assert "CMakeDeps: cmake_set_interface_link_directories is legacy, not necessary" in c.out
    c.run("create . --name=pkg --version=0.1 -c tools.cmake.cmakedeps:new=will_break_next")
    assert "CMakeConfigDeps: cmake_set_interface_link_directories deprecated and invalid. " \
           "The package 'package_info()' must correctly define the (CPS) information" in c.out

def test_consuming_cpp_info_with_components_dependency_from_same_package():
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            def package_info(self):
                self.cpp_info.components["lib"].type = 'shared-library'
                self.cpp_info.components["lib_extended"].type = 'shared-library'
                self.cpp_info.components["lib_extended"].requires = ['lib']
        """)
    c.save({"conanfile.py": conanfile,
            "test_package/conanfile.py": GenConanfile().with_settings("build_type")
                                                       .with_test("pass")
                                                       .with_generator("CMakeDeps")})
    c.run("create . --name=pkg --version=0.1 -c tools.cmake.cmakedeps:new=will_break_next")
    # it doesn't break
    assert "find_package(pkg)" in c.out


def test_consuming_cpp_info_with_components_dependency_from_other_package():
    c = TestClient()
    dep = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            name = "dep"
            version = "0.1"
            def package_info(self):
                self.cpp_info.components["lib"].type = 'shared-library'
    """)
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            requires = "dep/0.1"
            def package_info(self):
                self.cpp_info.components["lib"].type = 'shared-library'
                self.cpp_info.components["lib"].requires = ['dep::lib']
        """)
    c.save({"dep/conanfile.py": dep,
            "pkg/conanfile.py": conanfile,
            "pkg/test_package/conanfile.py": GenConanfile().with_settings("build_type")
                                                           .with_test("pass")
                                                           .with_generator("CMakeDeps")})
    c.run("create dep")
    c.run("create pkg --name=pkg --version=0.1 -c tools.cmake.cmakedeps:new=will_break_next")
    # it doesn't break
    assert "find_package(pkg)" in c.out


def test_consuming_cpp_info_transitively_by_requiring_root_component_in_another_component_from_another_package():
    c = TestClient()
    dependent_conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Dependent(ConanFile):
            settings = "os", "compiler", "arch", "build_type"
            name = 'dependent'
        """)

    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            settings = "os", "compiler", "arch", "build_type"
            def requirements(self):
                self.requires('dependent/0.1')
            def package_info(self):
                self.cpp_info.type = 'shared-library'
                self.cpp_info.requires = ['dependent::dependent']
        """)
    test_package = textwrap.dedent("""
        from conan import ConanFile
        class TestPkg(ConanFile):
            settings = "os", "compiler", "arch", "build_type"
            generators = "VirtualRunEnv", "CMakeDeps"

            def requirements(self):
                self.requires(self.tested_reference_str)

            def test(self):
                pass
        """)
    c.save({"dependent/conanfile.py": dependent_conanfile,
            "main/conanfile.py": conanfile,
            "main/test_package/conanfile.py":test_package})
    c.run("create ./dependent/ --name=dependent --version=0.1 -c tools.cmake.cmakedeps:new=will_break_next")
    c.run("create ./main/ --name=pkg --version=0.1 -c tools.cmake.cmakedeps:new=will_break_next")


def test_cmake_find_mode_deprecated():
    tc = TestClient()
    dep = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            name = "dep"
            version = "0.1"
            def package_info(self):
                # Having both is ok as the user expects that config would
                # be generated nonetheless
                self.cpp_info.set_property("cmake_find_mode", "module")
        """)
    tc.save({"conanfile.py": dep})
    tc.run("create .")
    args = f"-g CMakeDeps -c tools.cmake.cmakedeps:new={new_value}"
    tc.run(f"install --requires=dep/0.1 {args}")
    assert "CMakeConfigDeps does not support module find mode"
