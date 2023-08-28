import os
import textwrap

import pytest

from conans.test.utils.tools import TestClient

@pytest.mark.tool("cmake")
@pytest.mark.parametrize(
    "find_package_prefer_config", ["ON", "OFF", "", None],
)
@pytest.mark.parametrize(
    "config_name_consumer", ["Findhello.cmake", "hello-config.cmake"]
)
@pytest.mark.parametrize(
    "config_name_hello", ["Findhello.cmake", "hello-config.cmake"]
)
@pytest.mark.parametrize(
    "consumer_path", ["PREPEND", "APPEND", None]
)
@pytest.mark.parametrize(
    "cmake_subfolder", ["cmake",
                        "anyothername",
                        os.path.join("lib", "cmake"),
                        "lib",
                        "hello",
                        os.path.join("hello", "cmake")
                        ]
)
def test_cmaketoolchain_path_find_package(config_name_hello, config_name_consumer, find_package_prefer_config, consumer_path,cmake_subfolder):
    client = TestClient(path_with_spaces=False)
    find_hello = textwrap.dedent("""
        MESSAGE(STATUS "hello from {component}:{filename}")
        """)
    conanfile_hello = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.files import copy
        class TestConan(ConanFile):
            name = "hello"
            version = "0.1"
            exports_sources = "*"
            def package(self):
                copy(self, "*", self.source_folder, self.package_folder)
            def package_info(self):
                self.cpp_info.builddirs.append("{subfolder}")
        """.format(subfolder=cmake_subfolder))
    conanfile_consumer = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMake, CMakeToolchain
        import os
        class TestConan(ConanFile):
            name = "consumer"
            version = "1.0.0"
            settings = "os", "compiler", "build_type", "arch"
            exports_sources = "*"
            requires = "hello/0.1@"

            def generate(self):
                tc = CMakeToolchain(self)
                if "{value}" in ["ON","OFF",""]:
                    tc.blocks["find_paths"].values["find_package_prefer_config"] = "{value}"
                tc.generate()

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.install()
        """.format(value=find_package_prefer_config))

    if consumer_path in ["APPEND","PREPEND"]:
        path_customization = textwrap.dedent("""
            list({mode} CMAKE_MODULE_PATH ${CMAKE_CURRENT_SOURCE_DIR}/mymodules)
            list({mode} CMAKE_PREFIX_PATH ${CMAKE_CURRENT_SOURCE_DIR}/mymodules)
            """.replace("{mode}", str(consumer_path)))
    else:
        path_customization = ""

    cmake_consumer = textwrap.dedent("""\
        cmake_minimum_required(VERSION 3.15)
        project(MyHello CXX)
        %s
        message(STATUS "CMAKE_FIND_PACKAGE_PREFER_CONFIG '${CMAKE_FIND_PACKAGE_PREFER_CONFIG}'")
        message(STATUS "CMAKE_MODULE_PATH '${CMAKE_MODULE_PATH}'")
        message(STATUS "CMAKE_PREFIX_PATH '${CMAKE_PREFIX_PATH}'")
        set(CMAKE_FIND_DEBUG_MODE TRUE)
        find_package(hello REQUIRED)
        """ % path_customization)

    client.save({"hello/conanfile.py": conanfile_hello,
                 "hello/%s/%s" % (cmake_subfolder, config_name_hello): find_hello.format(component="hello", filename=config_name_hello),
                 "consumer/conanfile.py": conanfile_consumer,
                 "consumer/CMakeLists.txt": cmake_consumer,
                 "consumer/mymodules/%s" % config_name_consumer: find_hello.format(component="consumer", filename=config_name_consumer),
                 })

    client.run("export hello")
    client.run("create consumer --build=missing")

    if consumer_path == None:
        expected_component = "hello" # nothing from consumer must be found
    elif config_name_hello is config_name_consumer:
        if consumer_path == "PREPEND":
            expected_component = "consumer" # consumer path was prepended
        else:
            expected_component = "hello" # consumer path was appended
    else:
        filenames = (config_name_hello, config_name_consumer)
        if filenames == ("hello-config.cmake", "Findhello.cmake"):
            if find_package_prefer_config in ["ON", None]:
                expected_component = "hello"
            else:
                expected_component = "consumer"
        elif filenames == ("Findhello.cmake", "hello-config.cmake"):
            if find_package_prefer_config in ["ON", None]:
                expected_component = "consumer"
            else:
                expected_component = "hello"

    expected_filename = config_name_hello if (expected_component == "hello") else config_name_consumer
    assert "hello from {}:{}".format(expected_component, expected_filename) in client.out

    if find_package_prefer_config in ["", "OFF", "ON"]:
        assert "CMAKE_FIND_PACKAGE_PREFER_CONFIG '{}'".format(find_package_prefer_config) in client.out
    else:
        assert "CMAKE_FIND_PACKAGE_PREFER_CONFIG 'ON'" in client.out


@pytest.mark.tool("cmake")
@pytest.mark.parametrize(
    "prefer_config", [None, True, False, "None", ""]
)
def test_cmaketoolchain_path_prefer_config(prefer_config):
    client = TestClient(path_with_spaces=False)
    conanfile_dep= textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.files import copy
        class TestConan(ConanFile):
            name = "{name}"
            version = "0.1"
            exports_sources = "*"
            def package(self):
                copy(self, "*", self.source_folder, self.package_folder)
            def package_info(self):
                self.cpp_info.builddirs.append("cmakeconfig")
        """)

    find_dep= textwrap.dedent("""
        MESSAGE(STATUS "hello from {name}")
        """)

    find_cmake_helper= textwrap.dedent("""
        MESSAGE(STATUS "hello from cmake-helper {name}")
        find_package({name} CONFIG)
        """)
    conanfile_consumer = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMake, CMakeToolchain
        import os
        class TestConan(ConanFile):
            name = "consumer"
            version = "1.0.0"
            settings = "os", "compiler", "build_type", "arch"
            exports_sources = "*"
            requires = "hello/0.1@", "world/0.1@", "moon/0.1@"
            tool_requires = "cmake-helpers/0.1@"

            def generate(self):
                tc = CMakeToolchain(self)
                tc.generate()

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.install()
        """)

    profile = textwrap.dedent("""
        include(default)
        [conf]
        tools.cmake.cmaketoolchain:find_package_prefer_config={}
        """)

    cmake_consumer = textwrap.dedent("""\
        cmake_minimum_required(VERSION 3.15)
        project(MyHello CXX)
        LIST(PREPEND CMAKE_MODULE_PATH ${CMAKE_SOURCE_DIR}/cmakemodules/overwrite)
        LIST(APPEND CMAKE_MODULE_PATH ${CMAKE_SOURCE_DIR}/cmakemodules/fallback)
        find_package(hello)
        find_package(world)
        find_package(moon)
        """)

    client.save({"hello/conanfile.py": conanfile_dep.format(name="hello"),
                 "hello/cmakeconfig/hello-config.cmake": find_dep.format(name="hello"),
                 "world/conanfile.py": conanfile_dep.format(name="world"),
                 "world/cmakeconfig/world-config.cmake": find_dep.format(name="world"),
                 "moon/conanfile.py": conanfile_dep.format(name="moon"),
                 "moon/cmakeconfig/moon-config.cmake": find_dep.format(name="moon"),
                 "cmake-helpers/conanfile.py": conanfile_dep.format(name="cmake-helpers"),
                 "cmake-helpers/cmakeconfig/Findhello.cmake": find_cmake_helper.format(name="hello"),
                 "consumer/cmakemodules/overwrite/Findworld.cmake": find_dep.format(name="overwritten world"),
                 "consumer/cmakemodules/fallback/Findmoon.cmake": find_dep.format(name="fallback moon"),
                 "consumer/conanfile.py": conanfile_consumer,
                 "consumer/CMakeLists.txt": cmake_consumer,
                 "profile": profile.format(prefer_config)
                 })

    client.run("export hello")
    client.run("export world")
    client.run("export moon")
    client.run("export cmake-helpers")
    cmd = "create consumer --build=missing"
    if prefer_config is not None:
        cmd += " -pr:h=profile"
    client.run(cmd)

    if prefer_config in [None, True, "None", ""]:
        assert "hello from hello" in client.out
        assert "hello from world" in client.out
        assert "hello from moon" in client.out
    else:
        assert "hello from cmake-helper hello" in client.out # should be considered
        assert "hello from hello" in client.out # since find_package(CONFIG) in cmake-helper
        assert "hello from overwritten world" in client.out # should be considered
        assert "hello from world" not in client.out # no
        assert "hello from fallback moon" in client.out # module is considered first
        assert "hello from moon" not in client.out


