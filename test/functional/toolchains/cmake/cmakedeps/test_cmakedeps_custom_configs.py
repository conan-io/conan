import os
import platform
import textwrap
import unittest

import pytest

from conans.client.conf import get_default_settings_yml
from conan.test.assets.genconanfile import GenConanfile
from conan.test.assets.sources import gen_function_cpp
from conan.test.utils.tools import TestClient

from conans.util.files import save


@pytest.mark.tool("cmake")
@pytest.mark.skipif(platform.system() != "Windows", reason="Only for windows")
class CustomConfigurationTest(unittest.TestCase):
    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.cmake import CMakeDeps
        from conan.tools.files import copy
        class App(ConanFile):
            settings = "os", "arch", "compiler", "build_type"
            requires = "hello/0.1"

            def generate(self):
                cmake = CMakeDeps(self)
                if self.dependencies["hello"].options.shared:
                    cmake.configuration = "ReleaseShared"
                cmake.generate()

                config = str(self.settings.build_type)
                if self.dependencies["hello"].options.shared:
                    config = "ReleaseShared"
                src = os.path.join(self.dependencies["hello"].package_folder, "bin")
                dst = os.path.join(self.build_folder, config)
                copy(self, "*.dll", src, dst, keep_path=False)
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
        self.client.run("new cmake_lib -d name=hello -d version=0.1")
        self.client.run("create . -s compiler.version=191 "
                        "-s build_type=Release -o hello/*:shared=True -tf=\"\"")
        self.client.run("create . --name=hello --version=0.1 -s compiler.version=191 "
                        "-s build_type=Release -tf=\"\"")

        # Prepare the actual consumer package
        self.client.save({"conanfile.py": self.conanfile,
                          "CMakeLists.txt": self.cmakelist,
                          "app.cpp": self.app})

    def test_generator_multi(self):
        settings = {"compiler": "msvc",
                    "compiler.version": "191",
                    "compiler.runtime": "dynamic",
                    "arch": "x86_64",
                    "build_type": "Release",
                    }

        settings = " ".join('-s %s="%s"' % (k, v) for k, v in settings.items() if v)

        # Run the configure corresponding to this test case
        with self.client.chdir('build'):
            self.client.run("install .. %s -o hello/*:shared=True -of=." % settings)
            self.client.run("install .. %s -o hello/*:shared=False -of=." % settings)
            self.assertTrue(os.path.isfile(os.path.join(self.client.current_folder,
                                                        "hello-Target-releaseshared.cmake")))
            self.assertTrue(os.path.isfile(os.path.join(self.client.current_folder,
                                                        "hello-Target-release.cmake")))

            self.client.run_command('cmake .. -G "Visual Studio 15 Win64" --loglevel=DEBUG')
            self.assertIn("Found DLL and STATIC", self.client.out)
            self.client.run_command('cmake --build . --config Release')
            self.client.run_command(r"Release\\app.exe")
            self.assertIn("hello/0.1: Hello World Release!", self.client.out)
            self.assertIn("main: Release!", self.client.out)
            self.client.run_command('cmake --build . --config ReleaseShared')
            self.client.run_command(r"ReleaseShared\\app.exe")
            self.assertIn("hello/0.1: Hello World Release!", self.client.out)
            self.assertIn("main: Release!", self.client.out)


@pytest.mark.tool("cmake")
@pytest.mark.skipif(platform.system() != "Windows", reason="Only for windows")
class CustomSettingsTest(unittest.TestCase):
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMakeDeps

        class App(ConanFile):
            settings = "os", "arch", "compiler", "build_type"
            requires = "hello/0.1"
            generators = "CMakeToolchain"

            def generate(self):
                cmake = CMakeDeps(self)
                #cmake.configurations.append("MyRelease") # NOT NECESSARY!!!
                cmake.generate()
        """)

    app = gen_function_cpp(name="main", includes=["hello"], calls=["hello"])

    cmakelist = textwrap.dedent("""
        set(CMAKE_CONFIGURATION_TYPES Debug Release MyRelease CACHE STRING
            "Available build-types: Debug, Release and MyRelease")

        cmake_minimum_required(VERSION 3.15)
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
        settings = get_default_settings_yml()
        settings = settings.replace("build_type: [null, Debug, Release, ",
                                    "build_type: [null, Debug, MyRelease, ")
        save(self.client.cache.settings_path, settings)
        self.client.run("new cmake_lib -d name=hello -d version=0.1")
        cmake = self.client.load("CMakeLists.txt")

        cmake = cmake.replace("cmake_minimum_required", """
            set(CMAKE_CONFIGURATION_TYPES Debug MyRelease Release CACHE STRING "Types")

            cmake_minimum_required""")
        cmake = cmake.replace("add_library", textwrap.dedent("""
            set(CMAKE_CXX_FLAGS_MYRELEASE ${CMAKE_CXX_FLAGS_RELEASE})
            set(CMAKE_C_FLAGS_MYRELEASE ${CMAKE_C_FLAGS_RELEASE})
            set(CMAKE_EXE_LINKER_FLAGS_MYRELEASE ${CMAKE_EXE_LINKER_FLAGS_RELEASE})
            add_library"""))
        cmake = cmake.replace("PUBLIC_HEADER", "CONFIGURATIONS MyRelease\nPUBLIC_HEADER")
        self.client.save({"CMakeLists.txt": cmake})
        self.client.run("create . --name=hello --version=0.1 -s compiler.version=191 -s build_type=MyRelease "
                        "-s:b build_type=MyRelease -tf=\"\"")

        # Prepare the actual consumer package
        self.client.save({"conanfile.py": self.conanfile,
                          "CMakeLists.txt": self.cmakelist,
                          "app.cpp": self.app})

    def test_generator_multi(self):
        settings = {"compiler": "msvc",
                    "compiler.version": "191",
                    "compiler.runtime": "dynamic",
                    "arch": "x86_64",
                    "build_type": "MyRelease",
                    }

        settings_h = " ".join('-s %s="%s"' % (k, v) for k, v in settings.items())
        settings_b = " ".join('-s:b %s="%s"' % (k, v) for k, v in settings.items())

        # Run the configure corresponding to this test case
        build_directory = os.path.join(self.client.current_folder, "build").replace("\\", "/")
        with self.client.chdir(build_directory):
            self.client.run("install .. %s %s -of=." % (settings_h, settings_b))
            self.assertTrue(os.path.isfile(os.path.join(self.client.current_folder,
                                                        "hello-Target-myrelease.cmake")))

            self.client.run_command('cmake .. -G "Visual Studio 15" '
                                    '-DCMAKE_TOOLCHAIN_FILE=conan_toolchain.cmake')
            self.client.run_command('cmake --build . --config MyRelease')
            self.client.run_command(r"MyRelease\\app.exe")
            self.assertIn("hello/0.1: Hello World Release!", self.client.out)
            self.assertIn("main: Release!", self.client.out)


@pytest.mark.tool("cmake")
def test_changing_build_type():
    client = TestClient(path_with_spaces=False)
    dep_conanfile = textwrap.dedent(r"""
       import os
       from conan import ConanFile
       from conan.tools.files import copy, save

       class Dep(ConanFile):
           settings = "build_type"
           def build(self):
               save(self, "hello.h",
               '# include <iostream>\n'
               'void hello(){{std::cout<<"BUILD_TYPE={}!!";}}'.format(self.settings.build_type))
           def package(self):
               copy(self, "*.h", self.source_folder, os.path.join(self.package_folder, "include"))
           """)
    client.save({"conanfile.py": dep_conanfile})
    client.run("create . --name=dep --version=0.1 -s build_type=Release")
    client.run("create . --name=dep --version=0.1 -s build_type=Debug")

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

    # in MSVC multi-config -s pkg/*:build_type=Debug is not really necesary, toolchain do nothing
    # TODO: Challenge how to define consumer build_type for conanfile.txt
    client.run("install . -s pkg*:build_type=Debug -s build_type=Release")
    client.run_command("cmake . -DCMAKE_TOOLCHAIN_FILE=conan_toolchain.cmake -DCMAKE_BUILD_TYPE=Debug")
    client.run_command("cmake --build . --config Debug")
    cmd = os.path.join(".", "Debug", "app") if platform.system() == "Windows" else "./app"
    client.run_command(cmd)
    assert "main: Debug!" in client.out
    assert "BUILD_TYPE=Release!!" in client.out
