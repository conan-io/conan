import platform
import unittest

import os

from conans.test.utils.tools import TestClient
from nose.plugins.attrib import attr


conanfile_py = """
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"
    build_policy="missing"
    def package_info(self):
        self.cpp_info.cppflags = ["MyFlag1", "MyFlag2"]
"""

chatconanfile_py = """
from conans import ConanFile

class ChatConan(ConanFile):
    name = "Chat"
    version = "0.1"
    requires = "Hello/0.1@lasote/testing"
    build_policy="missing"
    def package_info(self):
        self.cpp_info.cppflags = ["MyChatFlag1", "MyChatFlag2"]
"""

conanfile = """[requires]
Hello/0.1@lasote/testing
"""

cmake = """set(CMAKE_CXX_COMPILER_WORKS 1)
set(CMAKE_CXX_ABI_COMPILED 1)
project(MyHello CXX)
cmake_minimum_required(VERSION 2.8.12)

include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
conan_basic_setup()

message(STATUS "CMAKE_CXX_FLAGS=${CMAKE_CXX_FLAGS}")
message(STATUS "CONAN_CXX_FLAGS=${CONAN_CXX_FLAGS}")
message(STATUS "HELLO_CXX_FLAGS=${HELLO_FLAGS}")
message(STATUS "CHAT_CXX_FLAGS=${CHAT_FLAGS}")
"""


@attr("slow")
class CMakeFlagsTest(unittest.TestCase):

    def _get_line(self, text, begin):
        lines = str(text).splitlines()
        begin = "-- %s=" % begin
        line = [l for l in lines if l.startswith(begin)][0]
        flags = line[len(begin):].strip()
        self.assertNotIn("'", flags)
        self.assertNotIn('"', flags)
        return flags

    def flags_test(self):
        client = TestClient()
        client.save({"conanfile.py": conanfile_py})
        client.run("export . lasote/testing")
        client.save({"conanfile.txt": conanfile,
                     "CMakeLists.txt": cmake}, clean_first=True)

        client.run('install . -g cmake')
        client.runner("cmake .", cwd=client.current_folder)
        cmake_cxx_flags = self._get_line(client.user_io.out, "CMAKE_CXX_FLAGS")
        self.assertTrue(cmake_cxx_flags.endswith("MyFlag1 MyFlag2"))
        self.assertIn("CONAN_CXX_FLAGS=MyFlag1 MyFlag2", client.user_io.out)

    def transitive_flags_test(self):
        client = TestClient()
        client.save({"conanfile.py": conanfile_py})
        client.run("export . lasote/testing")
        client.save({"conanfile.py": chatconanfile_py}, clean_first=True)
        client.run("export . lasote/testing")
        client.save({"conanfile.txt": conanfile.replace("Hello", "Chat"),
                     "CMakeLists.txt": cmake}, clean_first=True)

        client.run('install . -g cmake')
        client.runner("cmake .", cwd=client.current_folder)
        cmake_cxx_flags = self._get_line(client.user_io.out, "CMAKE_CXX_FLAGS")
        self.assertTrue(cmake_cxx_flags.endswith("MyFlag1 MyFlag2 MyChatFlag1 MyChatFlag2"))
        self.assertIn("CONAN_CXX_FLAGS=MyFlag1 MyFlag2 MyChatFlag1 MyChatFlag2",
                      client.user_io.out)

    def targets_flags_test(self):
        client = TestClient()
        client.save({"conanfile.py": conanfile_py})
        client.run("export . lasote/testing")
        cmake_targets = cmake.replace("conan_basic_setup()",
                                      "conan_basic_setup(TARGETS)\n"
                                      "get_target_property(HELLO_FLAGS CONAN_PKG::Hello"
                                      " INTERFACE_COMPILE_OPTIONS)")
        client.save({"conanfile.txt": conanfile,
                     "CMakeLists.txt": cmake_targets},
                    clean_first=True)

        client.run('install . -g cmake')
        client.runner("cmake .", cwd=client.current_folder)
        cmake_cxx_flags = self._get_line(client.user_io.out, "CMAKE_CXX_FLAGS")
        self.assertNotIn("My", cmake_cxx_flags)
        self.assertIn("CONAN_CXX_FLAGS=MyFlag1 MyFlag2", client.user_io.out)
        self.assertIn("HELLO_CXX_FLAGS=MyFlag1;MyFlag2;"
                      "$<$<CONFIG:Release>:;>;$<$<CONFIG:RelWithDebInfo>:;>;$<$<CONFIG:MinSizeRel>:;>;$<$<CONFIG:Debug>:;>", client.user_io.out)

    def targets_own_flags_test(self):
        client = TestClient()
        client.save({"conanfile.py": conanfile_py.replace('version = "0.1"',
                                                          'version = "0.1"\n'
                                                          '    settings = "compiler"')})
        client.run("export . lasote/testing")
        cmake_targets = cmake.replace("conan_basic_setup()",
                                      "conan_basic_setup(TARGETS)\n"
                                      "get_target_property(HELLO_FLAGS CONAN_PKG::Hello"
                                      " INTERFACE_COMPILE_OPTIONS)")
        client.save({"conanfile.txt": conanfile,
                     "CMakeLists.txt": cmake_targets},
                    clean_first=True)

        client.run('install . -g cmake')
        client.runner("cmake . -DCONAN_CXX_FLAGS=CmdCXXFlag", cwd=client.current_folder)
        cmake_cxx_flags = self._get_line(client.user_io.out, "CMAKE_CXX_FLAGS")
        self.assertNotIn("My", cmake_cxx_flags)
        self.assertIn("CmdCXXFlag", cmake_cxx_flags)
        self.assertIn("CONAN_CXX_FLAGS=MyFlag1 MyFlag2 CmdCXXFlag", client.user_io.out)
        self.assertIn("HELLO_CXX_FLAGS=MyFlag1;MyFlag2;"
                      "$<$<CONFIG:Release>:;>;$<$<CONFIG:RelWithDebInfo>:;>;$<$<CONFIG:MinSizeRel>:;>;$<$<CONFIG:Debug>:;>", client.user_io.out)

    def transitive_targets_flags_test(self):
        client = TestClient()
        client.save({"conanfile.py": conanfile_py})
        client.run("export . lasote/testing")
        client.save({"conanfile.py": chatconanfile_py}, clean_first=True)
        client.run("export . lasote/testing")
        cmake_targets = cmake.replace("conan_basic_setup()",
                                      "conan_basic_setup(TARGETS)\n"
                                      "get_target_property(HELLO_FLAGS CONAN_PKG::Hello"
                                      " INTERFACE_COMPILE_OPTIONS)\n"
                                      "get_target_property(CHAT_FLAGS CONAN_PKG::Chat"
                                      " INTERFACE_COMPILE_OPTIONS)\n")
        client.save({"conanfile.txt": conanfile.replace("Hello", "Chat"),
                     "CMakeLists.txt": cmake_targets},
                    clean_first=True)

        client.run('install . -g cmake')
        client.runner("cmake .", cwd=client.current_folder)

        cmake_cxx_flags = self._get_line(client.user_io.out, "CMAKE_CXX_FLAGS")
        self.assertNotIn("My", cmake_cxx_flags)
        self.assertIn("CONAN_CXX_FLAGS=MyFlag1 MyFlag2 MyChatFlag1 MyChatFlag2",
                      client.user_io.out)
        self.assertIn("HELLO_CXX_FLAGS=MyFlag1;MyFlag2;"
                      "$<$<CONFIG:Release>:;>;$<$<CONFIG:RelWithDebInfo>:;>;$<$<CONFIG:MinSizeRel>:;>;$<$<CONFIG:Debug>:;>", client.user_io.out)
        self.assertIn("CHAT_CXX_FLAGS=MyChatFlag1;MyChatFlag2;"
                      "$<$<CONFIG:Release>:;>;$<$<CONFIG:RelWithDebInfo>:;>;$<$<CONFIG:MinSizeRel>:;>;$<$<CONFIG:Debug>:;>", client.user_io.out)

    def cmake_test_needed_settings(self):
        conanfile = """
import os
from conans import ConanFile, CMake

class MyLib(ConanFile):
    name = "MyLib"
    version = "0.1"
    %s

    def build(self):
        cmake = CMake(self)
        """
        for settings_line in ('', 'settings="arch"', 'settings="compiler"'):
            client = TestClient()
            client.save({"conanfile.py": conanfile % settings_line})
            client.run("install .")
            client.run("build .", ignore_error=True)

            self.assertIn("You must specify compiler, compiler.version and arch in "
                          "your settings to use a CMake generator", client.user_io.out,)

    def cmake_shared_flag_test(self):
        conanfile = """
import os
from conans import ConanFile, CMake

class MyLib(ConanFile):
    name = "MyLib"
    version = "0.1"
    options = {"shared": [True, False]}
    default_options= "shared=%s"
    settings = "arch", "compiler"

    def build(self):
        cmake = CMake(self)
        if self.options.shared:
            assert(cmake.definitions["BUILD_SHARED_LIBS"] ==  "ON")
        else:
            assert(cmake.definitions["BUILD_SHARED_LIBS"] ==  "OFF")
        """
        client = TestClient()
        client.save({"conanfile.py": conanfile % "True"})
        client.run("build .", ignore_error=True)

        self.assertIn("conanbuildinfo.txt file not found", client.user_io.out)

        client.run("install .")
        client.run("build .")

        client.save({"conanfile.py": conanfile % "False"}, clean_first=True)
        client.run("install .")
        client.run("build .")

    def std_flag_applied_test(self):
        conanfile = """
import os
from conans import ConanFile, CMake
class MyLib(ConanFile):
    name = "MyLib"
    version = "0.1"
    settings = "arch", "compiler", "cppstd"
    generators = "cmake"

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()
        """
        client = TestClient()
        client.save({"conanfile.py": conanfile,
                     "mylib.cpp": "auto myfunc(){return 3;}",  # c++14 feature
                     "CMakeLists.txt": """
set(CMAKE_CXX_COMPILER_WORKS 1)
set(CMAKE_CXX_ABI_COMPILED 1)
project(MyHello CXX)
cmake_minimum_required(VERSION 2.8.12)
include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
conan_basic_setup()
add_library(mylib mylib.cpp)
target_link_libraries(mylib ${CONAN_LIBS})
"""})

        if platform.system() != "Windows":
            client.run("install . --install-folder=build -s cppstd=gnu98")
            error = client.run("build . --build-folder=build", ignore_error=True)
            self.assertTrue(error)
            self.assertIn("Error in build()", client.out)

            # Now specify c++14
            client.run("install . --install-folder=build -s cppstd=gnu14")
            client.run("build . --build-folder=build")
            self.assertIn("CPP STANDARD: 14 WITH EXTENSIONS ON", client.out)
            libname = "libmylib.a" if platform.system() != "Windows" else "mylib.lib"
            libpath = os.path.join(client.current_folder, "build", "lib", libname)
            self.assertTrue(os.path.exists(libpath))

        client.run("install . --install-folder=build -s cppstd=14")
        client.run("build . --build-folder=build")
        self.assertIn("CPP STANDARD: 14 WITH EXTENSIONS OFF", client.out)
        libname = "libmylib.a" if platform.system() != "Windows" else "mylib.lib"
        libpath = os.path.join(client.current_folder, "build", "lib", libname)
        self.assertTrue(os.path.exists(libpath))
