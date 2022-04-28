import textwrap
import pytest

from conans.test.utils.tools import TestClient

consumer = textwrap.dedent("""
from conans import ConanFile
from conan.tools.cmake import CMake

class Consumer(ConanFile):
    name = "consumer"
    version = "1.0"
    settings = "os", "compiler", "build_type", "arch"
    generators = "CMakeDeps", "CMakeToolchain"
    exports_sources = ["CMakeLists.txt"]
    requires = "hello/1.0"

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()
""")


@pytest.mark.tool_cmake
def test_global_alias():
    conanfile = textwrap.dedent("""
    from conans import ConanFile

    class Hello(ConanFile):
        name = "hello"
        version = "1.0"
        settings = "os", "compiler", "build_type", "arch"

        def package_info(self):
            # the default global target is "hello::hello"
            self.cpp_info.set_property("cmake_target_aliases", ["hello"])
    """)

    cmakelists = textwrap.dedent("""
    cmake_minimum_required(VERSION 3.15)
    project(test)

    find_package(hello REQUIRED)
    get_target_property(link_libraries hello INTERFACE_LINK_LIBRARIES)
    message("hello link libraries: ${link_libraries}")
    """)

    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run("create .")

    client.save({"conanfile.py": consumer, "CMakeLists.txt": cmakelists})
    client.run("create .")

    assert "hello link libraries: hello::hello" in client.out


@pytest.mark.tool_cmake
def test_component_alias():
    conanfile = textwrap.dedent("""
    from conans import ConanFile

    class Hello(ConanFile):
        name = "hello"
        version = "1.0"
        settings = "os", "compiler", "build_type", "arch"

        def package_info(self):
            self.cpp_info.components["buy"].set_property("cmake_target_aliases",
                ["hola::adios"])
    """)

    cmakelists = textwrap.dedent("""
    cmake_minimum_required(VERSION VERSION 3.15)
    project(test)

    find_package(hello REQUIRED)
    get_target_property(link_libraries hola::adios INTERFACE_LINK_LIBRARIES)
    message("hola::adios link libraries: ${link_libraries}")
    """)

    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run("create .")

    client.save({"conanfile.py": consumer, "CMakeLists.txt": cmakelists})
    client.run("create .")

    assert "hola::adios link libraries: hello::buy" in client.out


@pytest.mark.tool_cmake
def test_custom_name():
    conanfile = textwrap.dedent("""
    from conans import ConanFile

    class Hello(ConanFile):
        name = "hello"
        version = "1.0"
        settings = "os", "compiler", "build_type", "arch"

        def package_info(self):
            self.cpp_info.set_property("cmake_target_name", "ola::comprar")
            self.cpp_info.set_property("cmake_target_aliases", ["hello"])
    """)

    cmakelists = textwrap.dedent("""
    cmake_minimum_required(VERSION 3.15)
    project(test)

    find_package(hello REQUIRED)
    get_target_property(link_libraries hello INTERFACE_LINK_LIBRARIES)
    message("hello link libraries: ${link_libraries}")
    """)

    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run("create .")

    client.save({"conanfile.py": consumer, "CMakeLists.txt": cmakelists})
    client.run("create .")

    assert "hello link libraries: ola::comprar" in client.out


@pytest.mark.tool_cmake
def test_collide_global_alias():
    conanfile = textwrap.dedent("""
    from conans import ConanFile

    class Hello(ConanFile):
        name = "hello"
        version = "1.0"
        settings = "os", "compiler", "build_type", "arch"

        def package_info(self):
            # the default global target is "hello::hello"
            self.cpp_info.set_property("cmake_target_aliases", ["hello::hello"])
    """)

    cmakelists = textwrap.dedent("""
    cmake_minimum_required(VERSION 3.15)
    project(test)

    find_package(hello REQUIRED)
    """)

    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run("create .")

    client.save({"conanfile.py": consumer, "CMakeLists.txt": cmakelists})
    client.run("create .")

    assert "Target name 'hello::hello' already exists." in client.out


@pytest.mark.tool_cmake
def test_collide_component_alias():
    conanfile = textwrap.dedent("""
    from conans import ConanFile

    class Hello(ConanFile):
        name = "hello"
        version = "1.0"
        settings = "os", "compiler", "build_type", "arch"

        def package_info(self):
            self.cpp_info.components["buy"].set_property("cmake_target_aliases", ["hello::buy"])
    """)

    cmakelists = textwrap.dedent("""
    cmake_minimum_required(VERSION 3.15)
    project(test)

    find_package(hello REQUIRED)
    """)

    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run("create .")

    client.save({"conanfile.py": consumer, "CMakeLists.txt": cmakelists})
    client.run("create .")

    assert "Target name 'hello::buy' already exists." in client.out
