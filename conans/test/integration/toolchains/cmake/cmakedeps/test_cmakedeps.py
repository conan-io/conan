import os
import textwrap

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_package_from_system():
    """
    If a node declares "system_package" property, the CMakeDeps generator will skip generating
    the -config.cmake and the other files for that node but will keep the "find_dependency" for
    the nodes depending on it. That will cause that cmake looks for the config files elsewhere
    https://github.com/conan-io/conan/issues/8919"""
    client = TestClient()
    dep2 = str(GenConanfile().with_name("dep2").with_version("1.0")
               .with_settings("os", "arch", "build_type", "compiler"))
    dep2 += """
    def package_info(self):
        self.cpp_info.set_property("skip_deps_file", True)
        self.cpp_info.set_property("cmake_file_name", "custom_dep2")

    """
    client.save({"conanfile.py": dep2})
    client.run("create .")

    dep1 = GenConanfile().with_name("dep1").with_version("1.0").with_require("dep2/1.0")\
                         .with_settings("os", "arch", "build_type", "compiler")
    client.save({"conanfile.py": dep1})
    client.run("create .")

    consumer = GenConanfile().with_name("consumer").with_version("1.0").\
        with_require("dep1/1.0").with_generator("CMakeDeps").\
        with_settings("os", "arch", "build_type", "compiler")
    client.save({"conanfile.py": consumer})
    client.run("install .")
    assert os.path.exists(os.path.join(client.current_folder, "dep1-config.cmake"))
    assert not os.path.exists(os.path.join(client.current_folder, "dep2-config.cmake"))
    assert not os.path.exists(os.path.join(client.current_folder, "custom_dep2-config.cmake"))
    contents = client.load("dep1-release-x86_64-data.cmake")
    assert 'set(dep1_FIND_DEPENDENCY_NAMES ${dep1_FIND_DEPENDENCY_NAMES} custom_dep2)' in contents


def test_test_package():
    client = TestClient()
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . gtest/1.0@")
    client.run("create . cmake/1.0@")

    client.save({"conanfile.py": GenConanfile().with_build_requires("cmake/1.0").
                with_build_requirement("gtest/1.0", force_host_context=True)})

    client.run("export . pkg/1.0@")

    consumer = textwrap.dedent(r"""
        from conans import ConanFile
        class Pkg(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            generators = "CMakeDeps"
            requires = "pkg/1.0"
        """)
    client.save({"conanfile.py": consumer})
    client.run("install . -s:b os=Windows -s:h os=Linux --build=missing")
    cmake_data = client.load("pkg-release-x86_64-data.cmake")
    assert "gtest" not in cmake_data


def test_components_error():
    # https://github.com/conan-io/conan/issues/9331
    client = TestClient()

    conan_hello = textwrap.dedent("""
        import os
        from conans import ConanFile

        from conan.tools.files import save
        class Pkg(ConanFile):
            settings = "os", "arch", "compiler", "build_type"

            def layout(self):
                pass

            def package_info(self):
                self.cpp_info.components["say"].includedirs = ["include"]
            """)

    client.save({"conanfile.py": conan_hello})
    client.run("create . hello/1.0@")


def test_cpp_info_component_objects():
    client = TestClient()
    conan_hello = textwrap.dedent("""
        from conans import ConanFile
        class Pkg(ConanFile):
            settings = "os", "arch", "build_type"
            def package_info(self):
                self.cpp_info.components["say"].objects = ["/path/to/mycomponent.o"]
            """)

    client.save({"conanfile.py": conan_hello})
    client.run("create . hello/1.0@ -s arch=x86_64 -s build_type=Release")
    client.run(f"install hello/1.0@ -g CMakeDeps -s arch=x86_64 -s build_type=Release -if '{client.current_folder}'")
    with open(os.path.join(client.current_folder, "helloTarget-release.cmake")) as f:
        content = f.read()
        assert """set_property(TARGET hello::say PROPERTY INTERFACE_LINK_LIBRARIES
             $<$<CONFIG:Release>:${hello_say_LINK_LIBS_RELEASE}
             ${hello_say_LINKER_FLAGS_RELEASE}
             ${hello_say_OBJECTS_RELEASE}> APPEND)""" in content
