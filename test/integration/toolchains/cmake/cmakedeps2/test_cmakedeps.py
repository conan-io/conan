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
            def build(self):
                cmake = CMake(self)
                cmake.configure()
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
        from conan.tools.cmake import CMake
        class PkgConan(ConanFile):
            requires = "libb/1.0"
            settings = "os", "arch", "compiler", "build_type"
            generators = "CMakeDeps"
            def build(self):
                cmake = CMake(self)
                cmake.configure()
    """)
    c.save({"conanfile.py": conanfile}, clean_first=True)
    c.run(f"install . -c tools.cmake.cmakedeps:new={new_value}")
    cmake_paths = c.load("conan_cmakedeps_paths.cmake")
    cmake_paths.replace("\\", "/")
    assert re.search(r"list\(PREPEND CMAKE_PROGRAM_PATH \".*/libb.*/p/binb\"\)", cmake_paths)
    assert not re.search(r"list\(PREPEND CMAKE_PROGRAM_PATH /bina\"", cmake_paths)
    assert re.search(r"list\(PREPEND CMAKE_LIBRARY_PATH \".*/libb.*/p/libb\" \".*/liba.*/p/liba\"\)", cmake_paths)
    assert re.search(r"list\(PREPEND CMAKE_INCLUDE_PATH \".*/libb.*/p/includeb\" \".*/liba.*/p/includea\"\)", cmake_paths)


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


def test_cmakeconfigdeps_components():
    gtest = textwrap.dedent("""
    from conan import ConanFile
    from conan.tools.cmake import CMake, CMakeDeps, CMakeToolchain, cmake_layout
    from conan.tools.files import copy, get
    from conan.tools.scm import Version

    class GtestConan(ConanFile):
        name = "gtest"
        version = "1.16.0"
        package_type = "static-library"
        settings = "os", "compiler", "build_type", "arch"

        options = {
            "shared": [True, False],
            "build_gmock": [True, False],
            "no_main": [True, False],
            "debug_postfix": ["ANY"],
        }
        default_options = {
            "shared": True,
            "build_gmock": True,
            "no_main": False,
            "debug_postfix": "d",
        }

        def package(self):
            pass

        def package_info(self):
            postfix = self.options.get_safe("debug_prefix", "")
            self.cpp_info.set_property("cmake_file_name", "GTest")

            self.cpp_info.components["gtest"].set_property("cmake_target_name", "GTest::gtest")
            self.cpp_info.components["gtest"].set_property("cmake_target_aliases", ["GTest::GTest"])
            #self.cpp_info.components["gtest"].set_property("pkg_config_name", "gtest")
            self.cpp_info.components["gtest"].libs = [f"gtest{postfix}"]

            self.cpp_info.components["gtest"].type = self.package_type
            self.cpp_info.components["gtest"].location = f"bin/gtest{postfix}.dll" if self.options.shared else f"lib/gtest{postfix}.lib"
            self.cpp_info.components["gtest"].link_location = f"lib/gtest{postfix}.lib" if self.options.shared else None
            self.cpp_info.components["gtest"].languages = ["C++"]

            if self.options.shared:
                self.cpp_info.components["gtest"].defines.append("GTEST_LINKED_AS_SHARED_LIBRARY=1")

            if not self.options.no_main:
                self.cpp_info.components["gtest_main"].set_property("cmake_target_name", "GTest::gtest_main")
                self.cpp_info.components["gtest_main"].set_property("cmake_target_aliases", ["GTest::Main"])
                #self.cpp_info.components["gtest_main"].set_property("pkg_config_name", "gtest_main")
                self.cpp_info.components["gtest_main"].libs = [f"gtest_main{postfix}"]
                self.cpp_info.components["gtest_main"].requires = ["gtest"]

                self.cpp_info.components["gtest_main"].type = self.package_type
                self.cpp_info.components["gtest_main"].location = f"bin/gtest_main{postfix}.dll" if self.options.shared else f"lib/gtest_main{postfix}.lib"
                self.cpp_info.components["gtest_main"].link_location = f"lib/gtest_main{postfix}.lib" if self.options.shared else None
                self.cpp_info.components["gtest_main"].languages = ["C++"]

            # gmock
            if self.options.build_gmock:
                self.cpp_info.components["gmock"].set_property("cmake_target_name", "GTest::gmock")
                #self.cpp_info.components["gmock"].set_property("pkg_config_name", "gmock")
                self.cpp_info.components["gmock"].libs = [f"gmock{postfix}"]
                self.cpp_info.components["gmock"].requires = ["gtest"]

                self.cpp_info.components["gmock"].type = self.package_type
                self.cpp_info.components["gmock"].location = f"bin/gmock{postfix}.dll" if self.options.shared else f"lib/gmock{postfix}.lib"
                self.cpp_info.components["gmock"].link_location = f"lib/gmock{postfix}.lib" if self.options.shared else None
                self.cpp_info.components["gmock"].languages = ["C++"]


                # gmock_main
                if not self.options.no_main:
                    self.cpp_info.components["gmock_main"].set_property("cmake_target_name", "GTest::gmock_main")
                    #self.cpp_info.components["gmock_main"].set_property("pkg_config_name", "gmock_main")
                    self.cpp_info.components["gmock_main"].libs = [f"gmock_main{postfix}"]
                    self.cpp_info.components["gmock_main"].requires = ["gmock"]

                    self.cpp_info.components["gmock_main"].type = self.package_type
                    self.cpp_info.components["gmock_main"].location = f"bin/gmock_main{postfix}.dll" if self.options.shared else f"lib/gmock_main{postfix}.lib"
                    self.cpp_info.components["gmock_main"].link_location = f"lib/gmock_main{postfix}.lib" if self.options.shared else None
                    self.cpp_info.components["gmock_main"].languages = ["C++"]
        """)
    c = TestClient()
    c.save({"conanfile.py": gtest,
            "test_package/conanfile.py": GenConanfile().with_settings("build_type").with_generator("CMakeDeps").with_test("pass")})
    c.run("create . -c tools.cmake.cmakedeps:new=will_break_next")
    print(c.out)
