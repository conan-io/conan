import re
import textwrap

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient

new_value = "will_break_next"


@pytest.fixture
def client():
    c = TestClient()
    pkg = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMake, cmake_layout
        import os
        class Pkg(ConanFile):
            settings = "build_type", "os", "arch", "compiler"
            requires = "dep/0.1"
            generators = "CMakeDeps", "CMakeToolchain"
            def layout(self):  # Necessary to force config files in another location
                cmake_layout(self)
            def build(self):
                cmake = CMake(self)
                cmake.configure(variables={"CMAKE_FIND_DEBUG_MODE": "ON"})
       """)
    cmake = textwrap.dedent("""
       cmake_minimum_required(VERSION 3.15)
       project(pkgb LANGUAGES NONE)
       find_package(dep CONFIG REQUIRED)
       """)
    c.save({"dep/conanfile.py": GenConanfile("dep", "0.1"),
            "pkg/conanfile.py": pkg,
            "pkg/CMakeLists.txt": cmake})
    return c


@pytest.mark.tool("cmake")
def test_cmake_generated(client):
    c = client
    c.run("create dep")
    c.run(f"build pkg -c tools.cmake.cmakedeps:new={new_value}")
    assert "Conan toolchain: Including CMakeDeps generated conan_find_paths.cmake" in c.out
    assert "Conan: Target declared imported INTERFACE library 'dep::dep'" in c.out


@pytest.mark.tool("cmake")
@pytest.mark.parametrize("lowercase", [False, True])
def test_cmake_in_package(client, lowercase):
    c = client
    # same, but in-package
    f = "dep-config" if lowercase else "depConfig"
    dep = textwrap.dedent(f"""
        import os
        from conan import ConanFile
        from conan.tools.files import save
        class Pkg(ConanFile):
            name = "dep"
            version = "0.1"

            def package(self):
                content = 'message(STATUS "Hello from dep dep-Config.cmake!!!!!")'
                save(self, os.path.join(self.package_folder, "cmake", "{f}.cmake"), content)
            def package_info(self):
                self.cpp_info.set_property("cmake_find_mode", "none")
                self.cpp_info.builddirs = ["cmake"]
        """)

    c.save({"dep/conanfile.py": dep})
    c.run("create dep")
    c.run(f"build pkg -c tools.cmake.cmakedeps:new={new_value}")
    assert "Conan toolchain: Including CMakeDeps generated conan_find_paths.cmake" in c.out
    assert "Hello from dep dep-Config.cmake!!!!!" in c.out


class TestRuntimeDirs:

    def test_runtime_lib_dirs_multiconf(self):
        client = TestClient()
        app = GenConanfile().with_requires("dep/1.0").with_generator("CMakeDeps")\
            .with_settings("build_type")
        client.save({"lib/conanfile.py": GenConanfile(),
                     "dep/conanfile.py": GenConanfile("dep").with_requires("onelib/1.0",
                                                                           "twolib/1.0"),
                     "app/conanfile.py": app})
        client.run("create lib --name=onelib --version=1.0")
        client.run("create lib --name=twolib --version=1.0")
        client.run("create dep  --version=1.0")

        client.run(f'install app -s build_type=Release -c tools.cmake.cmakedeps:new={new_value}')
        client.run(f'install app -s build_type=Debug -c tools.cmake.cmakedeps:new={new_value}')

        contents = client.load("app/conan_cmakedeps_paths.cmake")
        pattern_lib_dirs = r"set\(CONAN_RUNTIME_LIB_DIRS ([^)]*)\)"
        runtime_lib_dirs = re.search(pattern_lib_dirs, contents).group(1)
        assert "<CONFIG:Release>" in runtime_lib_dirs
        assert "<CONFIG:Debug>" in runtime_lib_dirs


@pytest.mark.tool("cmake")
@pytest.mark.parametrize("requires, tool_requires", [(True, False), (False, True), (True, True)])
def test_cmaketoolchain_path_find_program(requires, tool_requires):
    """Test that executables in bindirs of tool_requires can be found with
    find_program() in consumer CMakeLists.
    """
    c = TestClient()

    conanfile = textwrap.dedent("""
        import os
        from conan.tools.files import copy
        from conan import ConanFile
        class TestConan(ConanFile):
            name = "tool"
            version = "1.0"
            exports_sources = "*"
            def package(self):
                copy(self, "*", self.source_folder, os.path.join(self.package_folder, "bin"))
    """)
    c.save({"conanfile.py": conanfile, "hello": "", "hello.exe": ""})
    c.run("create .")

    requires = 'requires = "tool/1.0"' if requires else ""
    tool_requires = 'tool_requires = "tool/1.0"' if tool_requires else ""
    conanfile = textwrap.dedent(f"""
        from conan import ConanFile
        from conan.tools.cmake import CMake
        class PkgConan(ConanFile):
            {requires}
            {tool_requires}
            settings = "os", "arch", "compiler", "build_type"
            generators = "CMakeToolchain", "CMakeDeps"
            def build(self):
                cmake = CMake(self)
                cmake.configure()
    """)
    consumer = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(MyHello)
        find_program(HELLOPROG hello)
        if(HELLOPROG)
            message(STATUS "Found hello prog: ${HELLOPROG}")
        endif()
    """)
    c.save({"conanfile.py": conanfile, "CMakeLists.txt": consumer}, clean_first=True)
    c.run(f"build . -c tools.cmake.cmakedeps:new={new_value}")
    assert "Found hello prog" in c.out
    if requires and tool_requires:
        assert "There is already a 'tool/1.0' package contributing to CMAKE_PROGRAM_PATH" in c.out
