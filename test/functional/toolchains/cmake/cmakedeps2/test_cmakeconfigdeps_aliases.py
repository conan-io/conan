import textwrap
import pytest

from conan.test.utils.tools import TestClient

new_value = "will_break_next"

consumer = textwrap.dedent("""
from conan import ConanFile
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


@pytest.mark.tool("cmake", "3.27")
def test_global_alias():
    conanfile = textwrap.dedent("""
    from conan import ConanFile

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
    project(test NONE)

    find_package(hello REQUIRED)
    get_target_property(_aliased_target hello ALIASED_TARGET)
    message("hello aliased target: ${_aliased_target}")
    """)

    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run(f"create . -c tools.cmake.cmakedeps:new={new_value}")

    client.save({"conanfile.py": consumer, "CMakeLists.txt": cmakelists})
    client.run(f"create . -c tools.cmake.cmakedeps:new={new_value}")

    assert "hello aliased target: hello::hello" in client.out


@pytest.mark.tool("cmake", "3.27")
def test_component_alias():
    conanfile = textwrap.dedent("""
    from conan import ConanFile

    class Hello(ConanFile):
        name = "hello"
        version = "1.0"
        settings = "os", "compiler", "build_type", "arch"

        def package_info(self):
            self.cpp_info.components["buy"].set_property("cmake_target_aliases",
                ["hola::adios"])
    """)

    cmakelists = textwrap.dedent("""
    cmake_minimum_required(VERSION 3.15)
    project(test NONE)

    find_package(hello REQUIRED)
    get_target_property(_aliased_target hola::adios ALIASED_TARGET)
    message("hola::adios aliased target: ${_aliased_target}")
    """)

    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run(f"create . -c tools.cmake.cmakedeps:new={new_value}")

    client.save({"conanfile.py": consumer, "CMakeLists.txt": cmakelists})
    client.run(f"create . -c tools.cmake.cmakedeps:new={new_value}")

    assert "hola::adios aliased target: hello::buy" in client.out


@pytest.mark.tool("cmake", "3.27")
def test_global_and_component_alias():
    conanfile = textwrap.dedent("""
    from conan import ConanFile

    class Hello(ConanFile):
        name = "hello"
        version = "1.0"
        settings = "os", "compiler", "build_type", "arch"

        def package_info(self):
            self.cpp_info.set_property("cmake_target_aliases", ["hola::hola"])
            self.cpp_info.components["buy"].set_property("cmake_target_aliases",
                ["hola::adios"])
    """)

    cmakelists = textwrap.dedent("""
    cmake_minimum_required(VERSION 3.15)
    project(test NONE)

    find_package(hello REQUIRED)
    get_target_property(_aliased_target hola::hola ALIASED_TARGET)
    message("hola::hola aliased target: ${_aliased_target}")
    """)

    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run(f"create . -c tools.cmake.cmakedeps:new={new_value}")

    client.save({"conanfile.py": consumer, "CMakeLists.txt": cmakelists})
    client.run(f"create . -c tools.cmake.cmakedeps:new={new_value}")

    assert "hola::hola aliased target: hello::hello" in client.out


@pytest.mark.tool("cmake", "3.27")
def test_custom_name():
    conanfile = textwrap.dedent("""
    from conan import ConanFile

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
    project(test NONE)

    find_package(hello REQUIRED)
    get_target_property(_aliased_target hello ALIASED_TARGET)
    message("hello aliased target: ${_aliased_target}")
    """)

    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run(f"create . -c tools.cmake.cmakedeps:new={new_value}")

    client.save({"conanfile.py": consumer, "CMakeLists.txt": cmakelists})
    client.run(f"create . -c tools.cmake.cmakedeps:new={new_value}")

    assert "hello aliased target: ola::comprar" in client.out


@pytest.mark.tool("cmake", "3.27")
def test_collide_global_alias():
    conanfile = textwrap.dedent("""
    from conan import ConanFile

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
    project(test NONE)

    find_package(hello REQUIRED)
    """)

    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run(f"create . -c tools.cmake.cmakedeps:new={new_value}")

    client.save({"conanfile.py": consumer, "CMakeLists.txt": cmakelists})
    client.run(f"create . -c tools.cmake.cmakedeps:new={new_value}", assert_error=True)

    assert f"Alias 'hello::hello' already defined as a target in hello/1.0" in client.out


@pytest.mark.tool("cmake", "3.27")
def test_collide_component_alias():
    conanfile = textwrap.dedent("""
    from conan import ConanFile

    class Hello(ConanFile):
        name = "hello"
        version = "1.0"
        settings = "os", "compiler", "build_type", "arch"

        def package_info(self):
            self.cpp_info.components["buy"].set_property("cmake_target_aliases", ["hello::buy"])
    """)

    cmakelists = textwrap.dedent("""
    cmake_minimum_required(VERSION 3.15)
    project(test NONE)

    find_package(hello REQUIRED)
    """)

    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run(f"create . -c tools.cmake.cmakedeps:new={new_value}")

    client.save({"conanfile.py": consumer, "CMakeLists.txt": cmakelists})
    client.run(f"create . -c tools.cmake.cmakedeps:new={new_value}", assert_error=True)

    assert "Alias 'hello::buy' already defined as a target in hello/1.0" in client.out


@pytest.mark.tool("cmake", "3.27")
def test_collide_component_alias_to_alias():
    conanfile = textwrap.dedent("""
    from conan import ConanFile

    class Hello(ConanFile):
        name = "hello"
        version = "1.0"
        settings = "os", "compiler", "build_type", "arch"

        def package_info(self):
            self.cpp_info.components["ola"].set_property("cmake_target_aliases", ["hello::foo"])
            self.cpp_info.components["buy"].set_property("cmake_target_aliases", ["hello::foo"])
    """)

    cmakelists = textwrap.dedent("""
    cmake_minimum_required(VERSION 3.15)
    project(test NONE)

    find_package(hello REQUIRED)
    """)

    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run(f"create . -c tools.cmake.cmakedeps:new={new_value}")

    client.save({"conanfile.py": consumer, "CMakeLists.txt": cmakelists})
    client.run(f"create . -c tools.cmake.cmakedeps:new={new_value}", assert_error=True)

    assert "Alias 'hello::foo' already defined in hello/1.0" in client.out
