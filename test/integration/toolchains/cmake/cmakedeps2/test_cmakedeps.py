import re
import textwrap

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
    assert "set(CMAKE_FIND_PACKAGE_PREFER_CONFIG ON)" in cmake_paths
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
    assert re.search(r"list\(PREPEND CMAKE_LIBRARY_PATH \".*/libb.*/p/libb\" \".*/liba.*/p/liba\"\)",
                     cmake_paths)
    assert re.search(r"list\(PREPEND CMAKE_INCLUDE_PATH \".*/libb.*/p/includeb\" "
                     r"\".*/liba.*/p/includea\"\)", cmake_paths)


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
    assert "set_property(TARGET lib::lib APPEND PROPERTY INTERFACE_LINK_LIBRARIES\n" \
           '             $<$<CONFIG:RELEASE>:my_system_cool_lib>)' in cmake


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
    c.run(f"create . --name=pkg --version=0.1 -c tools.cmake.cmakedeps:new={new_value}")
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
    c.run(f"create . --name=pkg --version=0.1 -c tools.cmake.cmakedeps:new={new_value}")
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
    c.run(f"create pkg --name=pkg --version=0.1 -c tools.cmake.cmakedeps:new={new_value}")
    # it doesn't break
    assert "find_package(pkg)" in c.out


def test_error_incorrect_component():
    # https://github.com/conan-io/conan/issues/18554
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            requires = "dep/0.1"
            def package_info(self):
                self.cpp_info.requires = ['dep::lib']
        """)
    c.save({"dep/conanfile.py": GenConanfile("dep", "0.1"),
            "pkg/conanfile.py": conanfile,
            "pkg/test_package/conanfile.py": GenConanfile().with_settings("build_type")
                                                           .with_generator("CMakeDeps")
                                                           .with_test("pass")})
    c.run("create dep")
    c.run(f"create pkg --name=pkg --version=0.1 -c tools.cmake.cmakedeps:new={new_value}",
          assert_error=True)
    assert ("ERROR: Error in generator 'CMakeDeps': pkg/0.1 recipe cpp_info did .requires to "
            "'dep::lib' but component 'lib' not found in dep") in c.out


def test_consuming_cpp_info_transitively_by_requiring_root_component():
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
            "main/test_package/conanfile.py": test_package})
    c.run("create ./dependent/ --name=dependent --version=0.1 "
          f"-c tools.cmake.cmakedeps:new={new_value}")
    c.run(f"create ./main/ --name=pkg --version=0.1 -c tools.cmake.cmakedeps:new={new_value}")


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


def test_requires_to_application():
    c = TestClient()
    automake = textwrap.dedent("""
        from conan import ConanFile
        class Dependent(ConanFile):
            name = "automake"
            version = "0.1"
            package_type = "application"
        """)

    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            name = "libtool"
            version = "0.1"
            package_type = "static-library"

            def requirements(self):
                self.requires('automake/0.1')
        """)
    test_package = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMake

        class TestPkg(ConanFile):
            settings = "os", "compiler", "arch", "build_type"
            generators = "CMakeDeps", "CMakeToolchain"

            def requirements(self):
                self.requires(self.tested_reference_str)

            def test(self):
                pass
        """)

    c.save({"automake/conanfile.py": automake,
            "libtool/conanfile.py": conanfile,
            "libtool/test_package/conanfile.py": test_package})
    c.run("create automake")
    c.run(f"create libtool -c tools.cmake.cmakedeps:new={new_value}")
    targets = c.load("libtool/test_package/libtool-Targets-release.cmake")
    # The libtool shouldn't depend on the automake::automake target
    assert "automake::automake" not in targets


def test_requires_to_application_component():
    c = TestClient()
    automake = textwrap.dedent("""
        from conan import ConanFile
        class Dependent(ConanFile):
            name = "automake"
            version = "0.1"
            package_type = "application"

            def package_info(self):
                self.cpp_info.components["myapp"].exe = "myapp"
                self.cpp_info.components["myapp"].location = "path/to/myapp"
                self.cpp_info.components["mylibapp"].type = "header-library"
        """)

    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            name = "libtool"
            version = "0.1"
            package_type = "static-library"

            def requirements(self):
                self.requires('automake/0.1')
            def package_info(self):
                self.cpp_info.requires = ["automake::mylibapp"]
        """)
    test_package = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMake

        class TestPkg(ConanFile):
            settings = "os", "compiler", "arch", "build_type"
            generators = "CMakeDeps", "CMakeToolchain"

            def requirements(self):
                self.requires(self.tested_reference_str)

            def test(self):
                pass
        """)

    c.save({"automake/conanfile.py": automake,
            "libtool/conanfile.py": conanfile,
            "libtool/test_package/conanfile.py": test_package})
    c.run("create automake")
    c.run(f"create libtool -c tools.cmake.cmakedeps:new={new_value}")
    targets = c.load("libtool/test_package/libtool-Targets-release.cmake")
    # The libtool shouldn't depend on the automake::automake target
    assert "automake::automake" not in targets
    assert "# Requirement automake::mylibapp => Full link: True" in targets
    assert "$<$<CONFIG:RELEASE>:automake::mylibapp>" in targets


def test_alias_cmakedeps_set_property():
    tc = TestClient()
    tc.save({"dep/conanfile.py": textwrap.dedent("""

        from conan import ConanFile
        class Dep(ConanFile):
            name = "dep"
            version = "1.0"
            settings = "os", "compiler", "build_type", "arch"
            def package_info(self):
                self.cpp_info.components["mycomp"].set_property("cmake_target_name",
                                                                "dep::mycomponent")
        """),
             "conanfile.py": textwrap.dedent("""
             from conan import ConanFile
             from conan.tools.cmake import CMakeDeps, CMake
             class Pkg(ConanFile):
                name = "pkg"
                version = "1.0"
                settings = "os", "compiler", "build_type", "arch"

                requires = "dep/1.0"

                def generate(self):
                    deps = CMakeDeps(self)
                    deps.set_property("dep", "cmake_target_aliases", ["alias", "dep::other_name"])
                    deps.set_property("dep::mycomp", "cmake_target_aliases",
                                      ["component_alias", "dep::my_aliased_component"])
                    deps.generate()
             """)})
    tc.run("create dep")
    tc.run(f"install . -c tools.cmake.cmakedeps:new={new_value}")
    targets_data = tc.load('dep-Targets-release.cmake')
    assert "add_library(dep::dep" in targets_data
    assert "add_library(alias" in targets_data
    assert "add_library(dep::other_name" in targets_data

    assert "add_library(component_alias" in targets_data
    assert "add_library(dep::my_aliased_component" in targets_data
