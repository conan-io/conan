import os
import platform
import shutil
import unittest

from conans.model.ref import ConanFileReference, PackageReference
from conans.test.utils.tools import TestClient, NO_SETTINGS_PACKAGE_ID, TurboTestClient, GenConanfile
from conans.util.files import load


class CMakePathsGeneratorTest(unittest.TestCase):

    def cmake_paths_contents_test(self):
        ref1 = ConanFileReference.loads("lib1/1.0@conan/stable")
        ref2 = ConanFileReference.loads("lib2/1.0@conan/stable")
        client = TurboTestClient()
        pref1 = client.create(ref1)
        pref2 = client.create(ref2, conanfile=GenConanfile().with_requirement(ref1))
        client.run("install {} -g cmake_paths".format(ref2))
        pfolder1 = client.cache.package_layout(pref1.ref).package(pref1).replace("\\", "/")
        pfolder2 = client.cache.package_layout(pref2.ref).package(pref2).replace("\\", "/")
        contents = load(os.path.join(client.current_folder, "conan_paths.cmake"))
        expected = 'set(CONAN_LIB2_ROOT "{pfolder2}")\r\n' \
                   'set(CONAN_LIB1_ROOT "{pfolder1}")\r\n' \
                   'set(CMAKE_MODULE_PATH "{pfolder2}/"\r\n\t\t\t"{pfolder1}/" ' \
                   '${{CMAKE_MODULE_PATH}} ${{CMAKE_CURRENT_LIST_DIR}})\r\n' \
                   'set(CMAKE_PREFIX_PATH "{pfolder2}/"\r\n\t\t\t"{pfolder1}/" ' \
                   '${{CMAKE_PREFIX_PATH}} ${{CMAKE_CURRENT_LIST_DIR}})'
        if platform.system() != "Windows":
            expected = expected.replace("\r", "")
        self.assertEqual(expected.format(pfolder1=pfolder1, pfolder2=pfolder2), contents)

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
MESSAGE("ROOT PATH: ${CONAN_HELLO0_ROOT}")
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
        with client.chdir(build_dir):
            ret = client.run_command("cmake ..")
        shutil.rmtree(build_dir)
        self.assertNotEqual(ret, 0)

        # With the toolchain everything is ok
        os.mkdir(build_dir)
        with client.chdir(build_dir):
            ret = client.run_command("cmake .. -DCMAKE_TOOLCHAIN_FILE=../conan_paths.cmake")
        self.assertEqual(ret, 0)
        self.assertIn("HELLO FROM THE Hello0 FIND PACKAGE!", client.out)
        ref = ConanFileReference.loads("Hello0/0.1@user/channel")
        pref = PackageReference(ref, NO_SETTINGS_PACKAGE_ID)
        package_folder = client.cache.package_layout(ref).package(pref)
        # Check that the CONAN_HELLO0_ROOT has been replaced with the real abs path
        self.assertIn("ROOT PATH: %s" % package_folder.replace("\\", "/"), client.out)

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
        ret = client.run_command("cmake .. ", cwd=build_dir)
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
        ret = client.run_command("cmake .. ", cwd=build_dir)
        self.assertEqual(ret, 0)
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
        ret = client.run_command("cmake .. ", cwd=build_dir)
        self.assertEqual(ret, 0)
        self.assertIn("HELLO FROM THE INSTALL FOLDER!", client.out)
