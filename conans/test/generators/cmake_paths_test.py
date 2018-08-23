import shutil
import unittest
import os
from collections import namedtuple

from conans.client.generators.cmake_paths import CMakePathsGenerator
from conans.model.build_info import CppInfo
from conans.model.conan_file import ConanFile
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient
from conans.model.env_info import EnvValues


class CMakePathsGeneratorTest(unittest.TestCase):

    def cmake_vars_unit_test(self):
        settings_mock = namedtuple("Settings", "build_type, os, os_build, constraint")
        settings = settings_mock("Release", None, None, lambda x, raise_undefined_field: x)
        conanfile = ConanFile(None, None)
        conanfile.initialize(settings, EnvValues())
        tmp = temp_folder()
        cpp_info = CppInfo(tmp)
        custom_dir = os.path.join(tmp, "custom_build_dir")
        os.mkdir(custom_dir)
        cpp_info.builddirs.append(os.path.join(tmp, "custom_build_dir"))
        conanfile.deps_cpp_info.update(cpp_info, "MyLib")

        generator = CMakePathsGenerator(conanfile)
        cmake_lines = [s.replace("\t\t\t", "").replace('\\', '/')
                       for s in generator.content.splitlines()]
        self.assertEquals('set(CMAKE_MODULE_PATH '
                          '"%s/"' % tmp.replace('\\', '/'), cmake_lines[0])
        self.assertEquals('"%s" ${CMAKE_MODULE_PATH} '
                          '${CMAKE_CURRENT_LIST_DIR})' % custom_dir.replace('\\', '/'),
                          cmake_lines[1])
        self.assertEquals('set(CMAKE_PREFIX_PATH '
                          '"%s/"' % tmp.replace('\\', '/'), cmake_lines[2])
        self.assertEquals('"%s" ${CMAKE_PREFIX_PATH} '
                          '${CMAKE_CURRENT_LIST_DIR})' % custom_dir.replace('\\', '/'),
                          cmake_lines[3])

    def cmake_paths_integration_test(self):
        """First package with own findHello0.cmake file"""
        client = TestClient()
        conanfile = """from conans import ConanFile
class TestConan(ConanFile):
    name = "Hello0"
    version = "0.1"
    exports = "*"

    def package(self):
        self.copy(pattern="*", keep_path=False)

"""
        files = {"conanfile.py": conanfile,
                 "FindHello0.cmake": """
SET(Hello0_FOUND 1)
MESSAGE("HELLO FROM THE Hello0 FIND PACKAGE!")
"""}
        client.save(files)
        client.run("create . user/channel")

        # Directly using CMake as a consumer we can find it with the "cmake_paths" generator
        files = {"CMakeLists.txt": """
set(CMAKE_CXX_COMPILER_WORKS 1)
set(CMAKE_CXX_ABI_COMPILED 1)
project(MyHello CXX)
cmake_minimum_required(VERSION 2.8)

find_package(Hello0 REQUIRED)

"""}
        client.save(files, clean_first=True)
        client.run("install Hello0/0.1@user/channel -g cmake_paths")
        self.assertTrue(os.path.exists(os.path.join(client.current_folder,
                                                    "conan_paths.cmake")))
        # Without the toolchain we cannot find the package
        build_dir = os.path.join(client.current_folder, "build")
        os.mkdir(build_dir)
        ret = client.runner("cmake ..", cwd=build_dir)
        shutil.rmtree(build_dir)
        self.assertNotEqual(ret, 0)

        # With the toolchain everything is ok
        os.mkdir(build_dir)
        ret = client.runner("cmake .. -DCMAKE_TOOLCHAIN_FILE=../conan_paths.cmake",
                            cwd=build_dir)
        self.assertEqual(ret, 0)
        self.assertIn("HELLO FROM THE Hello0 FIND PACKAGE!", client.out)

        # Now try without toolchain but including the file
        files = {"CMakeLists.txt": """
set(CMAKE_CXX_COMPILER_WORKS 1)
set(CMAKE_CXX_ABI_COMPILED 1)
project(MyHello CXX)
cmake_minimum_required(VERSION 2.8)
include(${CMAKE_BINARY_DIR}/../conan_paths.cmake)

find_package(Hello0 REQUIRED)

"""}
        client.save(files, clean_first=True)
        os.mkdir(build_dir)
        client.run("install Hello0/0.1@user/channel -g cmake_paths")
        ret = client.runner("cmake .. ", cwd=build_dir)
        self.assertEqual(ret, 0)
        self.assertIn("HELLO FROM THE Hello0 FIND PACKAGE!", client.out)

    def find_package_priority_test(self):
        """A package findXXX has priority over the CMake installation one and the curdir one"""
        client = TestClient()
        conanfile = """from conans import ConanFile
class TestConan(ConanFile):
    name = "Zlib"
    version = "0.1"
    exports = "*"

    def package(self):
        self.copy(pattern="*", keep_path=False)

"""
        files = {"conanfile.py": conanfile,
                 "FindZLIB.cmake": 'MESSAGE("HELLO FROM THE PACKAGE FIND PACKAGE!")'}
        client.save(files)
        client.run("create . user/channel")

        files = {"CMakeLists.txt": """
set(CMAKE_CXX_COMPILER_WORKS 1)
set(CMAKE_CXX_ABI_COMPILED 1)
project(MyHello CXX)
cmake_minimum_required(VERSION 2.8)
include(${CMAKE_BINARY_DIR}/../conan_paths.cmake)

find_package(ZLIB REQUIRED)

"""}
        build_dir = os.path.join(client.current_folder, "build")
        files["FindZLIB.cmake"] = 'MESSAGE("HELLO FROM THE INSTALL FOLDER!")'
        client.save(files, clean_first=True)
        os.mkdir(build_dir)
        client.run("install Zlib/0.1@user/channel -g cmake_paths")
        ret = client.runner("cmake .. ", cwd=build_dir)
        self.assertEquals(ret, 0)
        self.assertIn("HELLO FROM THE PACKAGE FIND PACKAGE!", client.out)

        # Now consume the zlib package as a require with the cmake_find_package
        # and the "cmake" generator. Should prioritize the one from the package.
        conanfile = """from conans import ConanFile, CMake
class TestConan(ConanFile):
    name = "Consumer"
    version = "0.1"
    exports = "*"
    settings = "compiler", "arch"
    generators = "cmake_find_package", "cmake"
    requires = "Zlib/0.1@user/channel"

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()

    def package(self):
        self.copy(pattern="*", keep_path=False)

"""
        files = {"conanfile.py": conanfile,
                 "CMakeLists.txt": """
set(CMAKE_CXX_COMPILER_WORKS 1)
set(CMAKE_CXX_ABI_COMPILED 1)
project(MyHello CXX)
cmake_minimum_required(VERSION 2.8)
include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
conan_basic_setup()

find_package(ZLIB REQUIRED)

"""}
        client.save(files, clean_first=True)
        client.run("create . user/channel")
        self.assertIn("HELLO FROM THE PACKAGE FIND PACKAGE!", client.out)
        self.assertNotIn("Conan: Using autogenerated FindZlib.cmake", client.out)

    def find_package_priority2_test(self):
        """A system findXXX has NOT priority over the install folder one,
        the zlib package do not package findZLIB.cmake"""
        client = TestClient()
        conanfile = """from conans import ConanFile
class TestConan(ConanFile):
    name = "Zlib"
    version = "0.1"
    exports = "*"

    def package(self):
        self.copy(pattern="*", keep_path=False)

"""
        files = {"conanfile.py": conanfile}
        client.save(files)
        client.run("create . user/channel")

        files = {"CMakeLists.txt": """
set(CMAKE_CXX_COMPILER_WORKS 1)
set(CMAKE_CXX_ABI_COMPILED 1)
project(MyHello CXX)
cmake_minimum_required(VERSION 2.8)
include(${CMAKE_BINARY_DIR}/../conan_paths.cmake)

find_package(ZLIB REQUIRED)

"""}
        build_dir = os.path.join(client.current_folder, "build")
        files["FindZLIB.cmake"] = 'MESSAGE("HELLO FROM THE INSTALL FOLDER!")'
        client.save(files, clean_first=True)
        os.mkdir(build_dir)
        client.run("install Zlib/0.1@user/channel -g cmake_paths")
        ret = client.runner("cmake .. ", cwd=build_dir)
        self.assertEquals(ret, 0)
        self.assertIn("HELLO FROM THE INSTALL FOLDER!", client.out)
