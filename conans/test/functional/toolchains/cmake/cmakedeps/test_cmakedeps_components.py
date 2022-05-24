import textwrap
import unittest

import pytest

from conans.test.utils.tools import TestClient


class PropagateSpecificComponents(unittest.TestCase):
    """
        Feature: recipes can declare the components they are consuming from their requirements,
        only those components should be propagated to their own consumers. If required components
        doesn't exist, Conan will fail:
         * Resolved versions/revisions of the requirement might provide different components or
           no components at all.
    """

    top = textwrap.dedent("""
        from conans import ConanFile

        class Recipe(ConanFile):
            name = "top"

            def package_info(self):
                self.cpp_info.components["cmp1"].libs = ["top_cmp1"]
                self.cpp_info.components["cmp2"].libs = ["top_cmp2"]
    """)

    middle = textwrap.dedent("""
        from conans import ConanFile

        class Recipe(ConanFile):
            name = "middle"
            requires = "top/version"
            def package_info(self):
                self.cpp_info.requires = ["top::cmp1"]
    """)

    app = textwrap.dedent("""
        from conans import ConanFile

        class Recipe(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            name = "app"
            requires = "middle/version"
        """)

    def setUp(self):
        client = TestClient()
        client.save({
            'top.py': self.top,
            'middle.py': self.middle,
            'app.py': self.app
        })
        client.run('create top.py top/version@')
        client.run('create middle.py middle/version@')
        self.cache_folder = client.cache_folder

    def test_cmakedeps_app(self):
        t = TestClient(cache_folder=self.cache_folder)
        t.save({'conanfile.py': self.app})
        t.run("install .  -g CMakeDeps")
        config = t.load("middle-Target-release.cmake")
        self.assertIn('top::cmp1', config)
        self.assertNotIn("top::top", config)

    def test_cmakedeps_multi(self):
        t = TestClient(cache_folder=self.cache_folder)
        t.run('install middle/version@ -g CMakeDeps')

        content = t.load('middle-release-x86_64-data.cmake')
        self.assertIn("list(APPEND middle_FIND_DEPENDENCY_NAMES top)", content)

        content = t.load('middle-Target-release.cmake')
        self.assertNotIn("top::top", content)
        self.assertNotIn("top::cmp2", content)
        self.assertIn("top::cmp1", content)


@pytest.fixture
def top_conanfile():
    return textwrap.dedent("""
        from conans import ConanFile

        class Recipe(ConanFile):
            name = "top"

            def package_info(self):
                self.cpp_info.components["cmp1"].libs = ["top_cmp1"]
                self.cpp_info.components["cmp2"].libs = ["top_cmp2"]
    """)


@pytest.mark.parametrize("from_component", [False, True])
def test_wrong_component(top_conanfile, from_component):
    """ If the requirement doesn't provide the component, it fails.
        We can only raise this error after the graph is fully resolved, it is when we
        know the actual components that the requirement is going to provide.
    """

    consumer = textwrap.dedent("""
        from conans import ConanFile

        class Recipe(ConanFile):
            requires = "top/version"
            def package_info(self):
                self.cpp_info.{}requires = ["top::not-existing"]
    """).format("components['foo']." if from_component else "")

    t = TestClient()
    t.save({'top.py': top_conanfile, 'consumer.py': consumer})
    t.run('create top.py top/version@')
    t.run('create consumer.py wrong/version@')

    t.run('install wrong/version@ -g CMakeDeps', assert_error=True)
    assert "Component 'top::not-existing' not found in 'top' package requirement" in t.out


def test_unused_requirement(top_conanfile):
    """ Requires should include all listed requirements
        This error is known when creating the package if the requirement is consumed.
    """
    consumer = textwrap.dedent("""
        from conans import ConanFile

        class Recipe(ConanFile):
            requires = "top/version"
            def package_info(self):
                self.cpp_info.requires = ["other::other"]
    """)
    t = TestClient()
    t.save({'top.py': top_conanfile, 'consumer.py': consumer})
    t.run('create top.py top/version@')
    t.run('create consumer.py wrong/version@', assert_error=True)
    assert "wrong/version package_info(): Package require 'top' not used in components " \
           "requires" in t.out


def test_wrong_requirement(top_conanfile):
    """ If we require a wrong requirement, we get a meaninful error.
        This error is known when creating the package if the requirement is not there.
    """
    consumer = textwrap.dedent("""
        from conans import ConanFile

        class Recipe(ConanFile):
            requires = "top/version"
            def package_info(self):
                self.cpp_info.requires = ["top::cmp1", "other::other"]
    """)
    t = TestClient()
    t.save({'top.py': top_conanfile, 'consumer.py': consumer})
    t.run('create top.py top/version@')
    t.run('create consumer.py wrong/version@', assert_error=True)
    assert "wrong/version package_info(): Package require 'other' declared in " \
           "components requires but not defined as a recipe requirement" in t.out


@pytest.mark.tool_cmake
def test_components_system_libs():
    conanfile = textwrap.dedent("""
        from conans import ConanFile

        class Requirement(ConanFile):
            name = "requirement"
            version = "system"

            settings = "os", "arch", "compiler", "build_type"

            def package_info(self):
                self.cpp_info.components["component"].system_libs = ["system_lib_component"]
    """)
    t = TestClient()
    t.save({"conanfile.py": conanfile})
    t.run("create .")

    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.cmake import CMake

        class Consumer(ConanFile):
            name = "consumer"
            version = "0.1"
            requires = "requirement/system"
            generators = "CMakeDeps", "CMakeToolchain"
            exports_sources = "CMakeLists.txt"
            settings = "os", "arch", "compiler", "build_type"

            def build(self):
                cmake = CMake(self)
                cmake.configure()
    """)

    cmakelists = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(consumer)

        find_package(requirement)
        get_target_property(tmp_libs requirement::component INTERFACE_LINK_LIBRARIES)
        get_target_property(tmp_options requirement::component INTERFACE_LINK_OPTIONS)
        message("component libs: ${tmp_libs}")
        message("component options: ${tmp_options}")
    """)

    t.save({"conanfile.py": conanfile, "CMakeLists.txt": cmakelists})
    t.run("create . --build missing -s build_type=Release")
    assert 'component libs: $<$<CONFIG:Release>:;system_lib_component>' in t.out
    assert ('component options: '
            '$<$<CONFIG:Release>:'
            '$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,SHARED_LIBRARY>:>;'
            '$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,MODULE_LIBRARY>:>;'
            '$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,EXECUTABLE>:>>') in t.out
    # NOTE: If there is no "conan install -s build_type=Debug", the properties won't contain the
    #       <CONFIG:Debug>


@pytest.mark.tool_cmake
def test_components_exelinkflags():
    conanfile = textwrap.dedent("""
        from conans import ConanFile

        class Requirement(ConanFile):
            name = "requirement"
            version = "system"

            settings = "os", "arch", "compiler", "build_type"

            def package_info(self):
                self.cpp_info.components["component"].exelinkflags = ["-Wl,-link1", "-Wl,-link2"]
    """)
    t = TestClient()
    t.save({"conanfile.py": conanfile})
    t.run("create .")

    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.cmake import CMake

        class Consumer(ConanFile):
            name = "consumer"
            version = "0.1"
            requires = "requirement/system"
            generators = "CMakeDeps", "CMakeToolchain"
            exports_sources = "CMakeLists.txt"
            settings = "os", "arch", "compiler", "build_type"

            def build(self):
                cmake = CMake(self)
                cmake.configure()
    """)

    cmakelists = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(consumer)
        find_package(requirement)
        get_target_property(tmp_options requirement::component INTERFACE_LINK_OPTIONS)
        message("component options: ${tmp_options}")
    """)

    t.save({"conanfile.py": conanfile, "CMakeLists.txt": cmakelists})
    t.run("create . --build missing -s build_type=Release")
    assert ('component options: '
            '$<$<CONFIG:Release>:'
            '$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,SHARED_LIBRARY>:>;'
            '$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,MODULE_LIBRARY>:>;'
            '$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,EXECUTABLE>:-Wl,-link1;-Wl,-link2>>') in t.out
    # NOTE: If there is no "conan install -s build_type=Debug", the properties won't contain the
    #       <CONFIG:Debug>


@pytest.mark.tool_cmake
def test_components_sharedlinkflags():
    conanfile = textwrap.dedent("""
        from conans import ConanFile

        class Requirement(ConanFile):
            name = "requirement"
            version = "system"

            settings = "os", "arch", "compiler", "build_type"

            def package_info(self):
                self.cpp_info.components["component"].sharedlinkflags = ["-Wl,-link1", "-Wl,-link2"]
    """)
    t = TestClient()
    t.save({"conanfile.py": conanfile})
    t.run("create .")

    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.cmake import CMake

        class Consumer(ConanFile):
            name = "consumer"
            version = "0.1"
            requires = "requirement/system"
            generators = "CMakeDeps", "CMakeToolchain"
            exports_sources = "CMakeLists.txt"
            settings = "os", "arch", "compiler", "build_type"

            def build(self):
                cmake = CMake(self)
                cmake.configure()
    """)

    cmakelists = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(consumer)
        find_package(requirement)
        get_target_property(tmp_options requirement::component INTERFACE_LINK_OPTIONS)
        message("component options: ${tmp_options}")
    """)

    t.save({"conanfile.py": conanfile, "CMakeLists.txt": cmakelists})
    t.run("create . --build missing -s build_type=Release")
    assert ('component options: '
            '$<$<CONFIG:Release>:'
            '$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,SHARED_LIBRARY>:-Wl,-link1;-Wl,-link2>;'
            '$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,MODULE_LIBRARY>:-Wl,-link1;-Wl,-link2>;'
            '$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,EXECUTABLE>:>>') in t.out
    # NOTE: If there is no "conan install -s build_type=Debug", the properties won't contain the
    #       <CONFIG:Debug>
