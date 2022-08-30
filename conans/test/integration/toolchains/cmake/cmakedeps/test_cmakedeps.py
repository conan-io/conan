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
        self.cpp_info.set_property("cmake_find_mode", "None")
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
    host_arch = client.get_default_host_profile().settings['arch']
    dep1_contents = client.load(f"dep1-release-{host_arch}-data.cmake")
    assert 'list(APPEND dep1_FIND_DEPENDENCY_NAMES custom_dep2)' in dep1_contents
    assert 'set(custom_dep2_FIND_MODE "")' in dep1_contents


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
    client.run("install . -s:b os=Windows -s:h os=Linux -s:h arch=x86_64 --build=missing")
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
                self.cpp_info.components["say"].objects = ["mycomponent.o"]
            """)

    client.save({"conanfile.py": conan_hello})
    client.run("create . hello/1.0@ -s arch=x86_64 -s build_type=Release")
    client.run("install hello/1.0@ -g CMakeDeps -s arch=x86_64 -s build_type=Release")
    with open(os.path.join(client.current_folder, "hello-Target-release.cmake")) as f:
        content = f.read()
        assert """set_property(TARGET hello::say
                     PROPERTY INTERFACE_LINK_LIBRARIES
                     $<$<CONFIG:Release>:${hello_hello_say_OBJECTS_RELEASE}>
                     $<$<CONFIG:Release>:${hello_hello_say_LIBRARIES_TARGETS}>
                     APPEND)""" in content
        # If there are componets, there is not a global cpp so this is not generated
        assert "hello_OBJECTS_RELEASE" not in content
        # But the global target is linked with the targets from the components
        assert "set_property(TARGET hello::hello PROPERTY INTERFACE_LINK_LIBRARIES " \
               "hello::say APPEND)" in content

    with open(os.path.join(client.current_folder, "hello-release-x86_64-data.cmake")) as f:
        content = f.read()
        # https://github.com/conan-io/conan/issues/11862
        # Global variables
        assert 'set(hello_OBJECTS_RELEASE "${hello_PACKAGE_FOLDER_RELEASE}/mycomponent.o")' \
               in content
        # But component variables
        assert 'set(hello_hello_say_OBJECTS_RELEASE "${hello_PACKAGE_FOLDER_RELEASE}/' \
               'mycomponent.o")' in content


def test_cpp_info_component_error_aggregate():
    # https://github.com/conan-io/conan/issues/10176
    # This test was consistently failing because "VirtualRunEnv" was not doing a "copy()"
    # of cpp_info before calling "aggregate_components()", and it was destructive, removing
    # components data
    client = TestClient()
    conan_hello = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            def package_info(self):
                self.cpp_info.components["say"].includedirs = ["include"]
            """)
    consumer = textwrap.dedent("""
        from conans import ConanFile
        class Pkg(ConanFile):
            settings = "os", "compiler", "arch", "build_type"
            requires = "hello/1.0"
            generators = "VirtualRunEnv", "CMakeDeps"
            def package_info(self):
                self.cpp_info.components["chat"].requires = ["hello::say"]
        """)
    test_package = textwrap.dedent("""
        from conans import ConanFile
        class Pkg(ConanFile):
            settings = "os", "compiler", "arch", "build_type"
            generators = "VirtualRunEnv", "CMakeDeps"

            def test(self):
                pass
        """)

    client.save({"hello/conanfile.py": conan_hello,
                 "consumer/conanfile.py": consumer,
                 "consumer/test_package/conanfile.py": test_package})
    client.run("create hello hello/1.0@")
    client.run("create consumer consumer/1.0@")
    assert "consumer/1.0 (test package): Running test()" in client.out


def test_cmakedeps_cppinfo_complex_strings():
    client = TestClient(path_with_spaces=False)
    conanfile = textwrap.dedent(r'''
        from conans import ConanFile
        class HelloLib(ConanFile):
            def package_info(self):
                self.cpp_info.defines.append("escape=partially \"escaped\"")
                self.cpp_info.defines.append("spaces=me you")
                self.cpp_info.defines.append("foobar=bazbuz")
                self.cpp_info.defines.append("answer=42")
        ''')
    client.save({"conanfile.py": conanfile})
    client.run("export . hello/1.0@")
    client.save({"conanfile.txt": "[requires]\nhello/1.0\n"}, clean_first=True)
    client.run("install . --build=missing -g CMakeDeps")
    arch = client.get_default_host_profile().settings['arch']
    deps = client.load(f"hello-release-{arch}-data.cmake")
    assert r"escape=partially \"escaped\"" in deps
    assert r"spaces=me you" in deps
    assert r"foobar=bazbuz" in deps
    assert r"answer=42" in deps
