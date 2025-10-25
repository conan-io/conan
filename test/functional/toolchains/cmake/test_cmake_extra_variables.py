import textwrap
import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient
new_value = "will_break_next"


@pytest.mark.tool("cmake", "3.27")
@pytest.mark.parametrize("generator", ["CMakeDeps", "CMakeConfigDeps"])
def test_package_info_extra_variables(generator):
    """ The dependencies can define extra variables to be used in CMake,
        but if the user is setting the cmake_extra_variables conf,
        those should have precedence.
    """
    client = TestClient()
    dep_conanfile = textwrap.dedent("""
        from conan import ConanFile

        class Pkg(ConanFile):
            name = "dep"
            version = "0.1"

            def package_info(self):
                self.cpp_info.set_property("cmake_extra_variables", {"FOO": 42})
    """)
    client.save({"dep/conanfile.py": dep_conanfile})
    client.run("create dep")

    cmakelists = textwrap.dedent("""
    cmake_minimum_required(VERSION 3.27)
    project(myproject CXX)
    find_package(dep CONFIG REQUIRED)
    message(STATUS "FOO=${FOO}")
    """)


    conanfile = textwrap.dedent(f"""
    from conan import ConanFile
    from conan.tools.cmake import CMake

    class Pkg(ConanFile):
        settings = "os", "arch", "compiler", "build_type"
        generators = "{generator}", "CMakeToolchain"
        requires = "dep/0.1"
        def build(self):
            cmake = CMake(self)
            cmake.configure()
    """)
    client.save({"CMakeLists.txt": cmakelists,
                 "conanfile.py": conanfile})
    conf = f"-c tools.cmake.cmakedeps:new={new_value}" if generator == "CMakeConfigDeps" else ""
    client.run(f"build . {conf} "
               """-c tools.cmake.cmaketoolchain:extra_variables="{'FOO': '9'}" """)

    assert "-- FOO=9" in client.out

