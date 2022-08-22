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
        arch = t.get_default_host_profile().settings['arch']
        content = t.load(f'middle-release-{arch}-data.cmake')
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
        get_target_property(tmp_deps requirement_requirement_component_DEPS_TARGET INTERFACE_LINK_LIBRARIES)
        message("component libs: ${tmp_libs}")
        message("component options: ${tmp_options}")
        message("component deps: ${tmp_deps}")
    """)

    t.save({"conanfile.py": conanfile, "CMakeLists.txt": cmakelists})
    t.run("create . --build missing -s build_type=Release")
    assert 'component libs: $<$<CONFIG:Release>:>;$<$<CONFIG:Release>:>;requirement_requirement_component_DEPS_TARGET' in t.out
    assert 'component deps: $<$<CONFIG:Release>:>;$<$<CONFIG:Release>:system_lib_component>;' in t.out
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


@pytest.mark.tool_cmake
def test_cmake_add_subdirectory():
    """https://github.com/conan-io/conan/issues/11743
       https://github.com/conan-io/conan/issues/11755"""

    t = TestClient()
    boost = textwrap.dedent("""
        from conan import ConanFile

        class Consumer(ConanFile):
            name = "boost"
            version = "1.0"

            def package_info(self):
                self.cpp_info.set_property("cmake_file_name", "Boost")
                self.cpp_info.components["A"].system_libs = ["A_1", "A_2"]
                self.cpp_info.components["B"].system_libs = ["B_1", "B_2"]
    """)
    t.save({"conanfile.py": boost})
    t.run("create .")
    conanfile = textwrap.dedent("""
            from conans import ConanFile
            from conan.tools.cmake import CMake, cmake_layout

            class Consumer(ConanFile):
                name = "consumer"
                version = "0.1"
                requires = "boost/1.0"
                generators = "CMakeDeps", "CMakeToolchain"
                settings = "os", "arch", "compiler", "build_type"

                def layout(self):
                    cmake_layout(self)

                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
        """)

    cmakelists = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.15)
            project(hello CXX)
            find_package(Boost CONFIG)
            add_subdirectory(src)

    """)
    sub_cmakelists = textwrap.dedent("""
            find_package(Boost REQUIRED COMPONENTS exception headers)

            message("AGGREGATED LIBS: ${Boost_LIBRARIES}")
            get_target_property(tmp boost::boost INTERFACE_LINK_LIBRARIES)
            message("AGGREGATED LINKED: ${tmp}")

            get_target_property(tmp boost::B INTERFACE_LINK_LIBRARIES)
            message("BOOST_B LINKED: ${tmp}")

            get_target_property(tmp boost::A INTERFACE_LINK_LIBRARIES)
            message("BOOST_A LINKED: ${tmp}")

            get_target_property(tmp boost_boost_B_DEPS_TARGET INTERFACE_LINK_LIBRARIES)
            message("BOOST_B_DEPS LINKED: ${tmp}")

            get_target_property(tmp boost_boost_A_DEPS_TARGET INTERFACE_LINK_LIBRARIES)
            message("BOOST_A_DEPS LINKED: ${tmp}")

    """)

    t.save({"conanfile.py": conanfile,
            "CMakeLists.txt": cmakelists, "src/CMakeLists.txt": sub_cmakelists})
    t.run("install .")
    # only doing the configure failed before #11743 fix
    t.run("build .")
    # The boost::boost target has linked the two components
    assert "AGGREGATED LIBS: boost::boost" in t.out
    assert "AGGREGATED LINKED: boost::B;boost::A" in t.out
    assert "BOOST_B LINKED: $<$<CONFIG:Release>:>;$<$<CONFIG:Release>:>;boost_boost_B_DEPS_TARGET" in t.out
    assert "BOOST_A LINKED: $<$<CONFIG:Release>:>;$<$<CONFIG:Release>:>;boost_boost_A_DEPS_TARGET" in t.out
    assert "BOOST_B_DEPS LINKED: $<$<CONFIG:Release>:>;$<$<CONFIG:Release>:B_1;B_2>" in t.out
    assert "BOOST_A_DEPS LINKED: $<$<CONFIG:Release>:>;$<$<CONFIG:Release>:A_1;A_2>;" in t.out
