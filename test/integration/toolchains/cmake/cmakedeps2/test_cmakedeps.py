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
