import textwrap
import pytest

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
    message(STATUS "BAR=${BAR}")
    message(STATUS "BAZ=${BAZ}")
    message(STATUS "BAR_CACHE=${BAR_CACHE}")
    message(STATUS "BAZ_CACHE=${BAZ_CACHE}")
    message(STATUS "BAR_CACHE_FORCE=${BAR_CACHE_FORCE}")
    """)

    conanfile = textwrap.dedent(f"""
    from conan import ConanFile
    from conan.tools.cmake import CMake, {generator}, CMakeToolchain

    class Pkg(ConanFile):
        settings = "os", "arch", "compiler", "build_type"
        requires = "dep/0.1"

        def generate(self):
            deps = {generator}(self)
            deps.generate()
            tc = CMakeToolchain(self)
            tc.cache_variables["BAR"] = "42"
            tc.variables["BAZ"] = "42"
            tc.cache_variables["BAR_CACHE"] = "42"
            tc.variables["BAZ_CACHE"] = "42"
            tc.cache_variables["BAR_CACHE_FORCE"] = "42"
            tc.generate()

        def build(self):
            cmake = CMake(self)
            cmake.configure()
    """)
    client.save({"CMakeLists.txt": cmakelists,
                 "conanfile.py": conanfile})
    conf = f"-c tools.cmake.cmakedeps:new={new_value}" if generator == "CMakeConfigDeps" else ""
    client.run(f"build . {conf} "
               """-c tools.cmake.cmaketoolchain:extra_variables="{'FOO': '9', 'BAR': '9', 'BAZ': '9', 'BAR_CACHE': {'value': '9', 'cache': True, 'type': 'STRING'}, 'BAZ_CACHE': {'value': '9', 'cache': True, 'type': 'STRING'}, 'BAR_CACHE_FORCE': {'value': '9', 'cache': True, 'type': 'STRING', 'force': True}}" """)

    assert "-- FOO=9" in client.out
    assert "-- BAR=9" in client.out
    assert "-- BAZ=9" in client.out
    # No overwrite in this case. Cache - Cache keeps the first occurrence in the file, can't override
    # from the profile
    assert "-- BAR_CACHE=42" in client.out
    assert "-- BAZ_CACHE=9" in client.out
    assert "-- BAR_CACHE_FORCE=9" in client.out

