import os
import platform
import textwrap
import unittest

import pytest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.assets.sources import gen_function_cpp
from conans.test.utils.tools import TestClient

from conans.util.files import save, load


@pytest.mark.tool_cmake
@pytest.mark.skipif(platform.system() != "Windows", reason="Only for windows")
class CustomConfigurationTest(unittest.TestCase):
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.cmake import CMakeDeps
        class App(ConanFile):
            settings = "os", "arch", "compiler", "build_type"
            requires = "hello/0.1"

            def generate(self):
                cmake = CMakeDeps(self)
                if self.options["hello"].shared:
                    cmake.configuration = "ReleaseShared"
                cmake.generate()

            def imports(self):
                config = str(self.settings.build_type)
                if self.options["hello"].shared:
                    config = "ReleaseShared"
                self.copy("*.dll", src="bin", dst=config, keep_path=False)
        """)

    app = gen_function_cpp(name="main", includes=["hello"], calls=["hello"])

    cmakelist = textwrap.dedent("""
        set(CMAKE_CONFIGURATION_TYPES Debug Release ReleaseShared CACHE STRING
            "Available build-types: Debug, Release and ReleaseShared")

        cmake_minimum_required(VERSION 2.8)
        project(App C CXX)

        set(CMAKE_PREFIX_PATH ${CMAKE_BINARY_DIR} ${CMAKE_PREFIX_PATH})
        set(CMAKE_MODULE_PATH ${CMAKE_BINARY_DIR} ${CMAKE_MODULE_PATH})

        set(CMAKE_CXX_FLAGS_RELEASESHARED ${CMAKE_CXX_FLAGS_RELEASE})
        set(CMAKE_C_FLAGS_RELEASESHARED ${CMAKE_C_FLAGS_RELEASE})
        set(CMAKE_EXE_LINKER_FLAGS_RELEASESHARED ${CMAKE_EXE_LINKER_FLAGS_RELEASE})

        find_package(hello REQUIRED)
        add_executable(app app.cpp)
        target_link_libraries(app PRIVATE hello::hello)
        """)

    def setUp(self):
        self.client = TestClient(path_with_spaces=False)
        self.client.run("new hello/0.1 -s")
        self.client.run("create . hello/0.1@ -s compiler.version=15 "
                        "-s build_type=Release -o hello:shared=True")
        self.client.run("create . hello/0.1@ -s compiler.version=15 "
                        "-s build_type=Release")

        # Prepare the actual consumer package
        self.client.save({"conanfile.py": self.conanfile,
                          "CMakeLists.txt": self.cmakelist,
                          "app.cpp": self.app})

    def test_generator_multi(self):
        settings = {"compiler": "Visual Studio",
                    "compiler.version": "15",
                    "arch": "x86_64",
                    "build_type": "Release",
                    }

        settings = " ".join('-s %s="%s"' % (k, v) for k, v in settings.items() if v)

        # Run the configure corresponding to this test case
        with self.client.chdir('build'):
            self.client.run("install .. %s -o hello:shared=True" % settings)
            self.client.run("install .. %s -o hello:shared=False" % settings)
            self.assertTrue(os.path.isfile(os.path.join(self.client.current_folder,
                                                        "hello-Target-releaseshared.cmake")))
            self.assertTrue(os.path.isfile(os.path.join(self.client.current_folder,
                                                        "hello-Target-release.cmake")))

            self.client.run_command('cmake .. -G "Visual Studio 15 Win64"')
            self.client.run_command('cmake --build . --config Release')
            self.client.run_command(r"Release\\app.exe")
            self.assertIn("hello/0.1: Hello World Release!", self.client.out)
            self.assertIn("main: Release!", self.client.out)
            self.client.run_command('cmake --build . --config ReleaseShared')
            self.client.run_command(r"ReleaseShared\\app.exe")
            self.assertIn("hello/0.1: Hello World Release!", self.client.out)
            self.assertIn("main: Release!", self.client.out)


@pytest.mark.tool_cmake
@pytest.mark.skipif(platform.system() != "Windows", reason="Only for windows")
class CustomSettingsTest(unittest.TestCase):
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.cmake import CMakeDeps

        class App(ConanFile):
            settings = "os", "arch", "compiler", "build_type"
            requires = "hello/0.1"

            def generate(self):
                cmake = CMakeDeps(self)
                #cmake.configurations.append("MyRelease") # NOT NECESSARY!!!
                cmake.generate()
        """)

    app = gen_function_cpp(name="main", includes=["hello"], calls=["hello"])

    cmakelist = textwrap.dedent("""
        set(CMAKE_CONFIGURATION_TYPES Debug Release MyRelease CACHE STRING
            "Available build-types: Debug, Release and MyRelease")

        cmake_minimum_required(VERSION 2.8)
        project(App C CXX)

        set(CMAKE_PREFIX_PATH ${CMAKE_BINARY_DIR} ${CMAKE_PREFIX_PATH})
        set(CMAKE_MODULE_PATH ${CMAKE_BINARY_DIR} ${CMAKE_MODULE_PATH})

        set(CMAKE_CXX_FLAGS_MYRELEASE ${CMAKE_CXX_FLAGS_RELEASE})
        set(CMAKE_C_FLAGS_MYRELEASE ${CMAKE_C_FLAGS_RELEASE})
        set(CMAKE_EXE_LINKER_FLAGS_MYRELEASE ${CMAKE_EXE_LINKER_FLAGS_RELEASE})

        find_package(hello REQUIRED)
        add_executable(app app.cpp)
        target_link_libraries(app PRIVATE hello::hello)
        """)

    def setUp(self):
        self.client = TestClient(path_with_spaces=False)
        settings = load(self.client.cache.settings_path)
        settings = settings.replace("Release", "MyRelease")
        save(self.client.cache.settings_path, settings)
        self.client.run("new hello/0.1 -s")
        cmake = self.client.load("src/CMakeLists.txt")

        cmake = cmake.replace("cmake_minimum_required", """
            set(CMAKE_CONFIGURATION_TYPES Debug MyRelease Release CACHE STRING "Types")

            cmake_minimum_required""")
        cmake = cmake.replace("conan_basic_setup()", """
            conan_basic_setup()
            set(CMAKE_CXX_FLAGS_MYRELEASE ${CMAKE_CXX_FLAGS_RELEASE})
            set(CMAKE_C_FLAGS_MYRELEASE ${CMAKE_C_FLAGS_RELEASE})
            set(CMAKE_EXE_LINKER_FLAGS_MYRELEASE ${CMAKE_EXE_LINKER_FLAGS_RELEASE})
            """)
        self.client.save({"src/CMakeLists.txt": cmake})
        self.client.run("create . hello/0.1@ -s compiler.version=15 -s build_type=MyRelease")

        # Prepare the actual consumer package
        self.client.save({"conanfile.py": self.conanfile,
                          "CMakeLists.txt": self.cmakelist,
                          "app.cpp": self.app})

    def test_generator_multi(self):
        settings = {"compiler": "Visual Studio",
                    "compiler.version": "15",
                    "arch": "x86_64",
                    "build_type": "MyRelease",
                    }

        settings = " ".join('-s %s="%s"' % (k, v) for k, v in settings.items() if v)

        # Run the configure corresponding to this test case
        build_directory = os.path.join(self.client.current_folder, "build").replace("\\", "/")
        with self.client.chdir(build_directory):
            self.client.run("install .. %s" % settings)
            self.assertTrue(os.path.isfile(os.path.join(self.client.current_folder,
                                                        "hello-Target-myrelease.cmake")))

            self.client.run_command('cmake .. -G "Visual Studio 15 Win64"')
            self.client.run_command('cmake --build . --config MyRelease')
            self.client.run_command(r"MyRelease\\app.exe")
            self.assertIn("hello/0.1: Hello World Release!", self.client.out)
            self.assertIn("main: Release!", self.client.out)


@pytest.mark.tool_cmake
def test_changing_build_type():
    client = TestClient(path_with_spaces=False)
    dep_conanfile = textwrap.dedent(r"""
       from conans import ConanFile
       from conans.tools import save

       class Dep(ConanFile):
           settings = "build_type"
           def build(self):
               save("hello.h",
               '# include <iostream>\n'
               'void hello(){{std::cout<<"BUILD_TYPE={}!!";}}'.format(self.settings.build_type))
           def package(self):
               self.copy("*.h", dst="include")
           """)
    client.save({"conanfile.py": dep_conanfile})
    client.run("create . dep/0.1@ -s build_type=Release")
    client.run("create . dep/0.1@ -s build_type=Debug")

    cmakelists = textwrap.dedent("""
        set(CMAKE_CXX_COMPILER_WORKS 1)
        set(CMAKE_CXX_ABI_COMPILED 1)
        cmake_minimum_required(VERSION 3.15)
        project(App CXX)

        # NOTE: NO MAP necessary!!!
        find_package(dep REQUIRED)
        add_executable(app app.cpp)
        target_link_libraries(app PRIVATE dep::dep)
        """)
    app = gen_function_cpp(name="main", includes=["hello"], calls=["hello"])
    pkg_conanfile = GenConanfile("pkg", "0.1").with_requires("dep/0.1").\
        with_generator("CMakeDeps").with_generator("CMakeToolchain").\
        with_settings("os", "compiler", "arch", "build_type")
    client.save({"conanfile.py": pkg_conanfile,
                 "CMakeLists.txt": cmakelists,
                 "app.cpp": app}, clean_first=True)

    # in MSVC multi-config -s pkg:build_type=Debug is not really necesary, toolchain do nothing
    # TODO: Challenge how to define consumer build_type for conanfile.txt
    client.run("install . -s pkg:build_type=Debug -s build_type=Release")
    client.run_command("cmake . -DCMAKE_TOOLCHAIN_FILE=conan_toolchain.cmake -DCMAKE_BUILD_TYPE=Debug")
    client.run_command("cmake --build . --config Debug")
    cmd = os.path.join(".", "Debug", "app") if platform.system() == "Windows" else "./app"
    client.run_command(cmd)
    assert "main: Debug!" in client.out
    assert "BUILD_TYPE=Release!!" in client.out

