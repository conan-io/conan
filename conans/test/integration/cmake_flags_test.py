import unittest
from conans.test.tools import TestClient
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

cmake = """
project(MyHello)
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

    def flags_test(self):
        client = TestClient()
        client.save({"conanfile.py": conanfile_py})
        client.run("export lasote/testing")
        client.save({"conanfile.txt": conanfile,
                     "CMakeLists.txt": cmake}, clean_first=True)

        client.run('install -g cmake')
        client.runner("cmake .", cwd=client.current_folder)
        self.assertIn("CMAKE_CXX_FLAGS=/DWIN32 /D_WINDOWS /W3 /GR /EHsc MyFlag1 MyFlag2",
                      client.user_io.out)
        self.assertIn("CONAN_CXX_FLAGS=MyFlag1 MyFlag2", client.user_io.out)

    def transitive_flags_test(self):
        client = TestClient()
        client.save({"conanfile.py": conanfile_py})
        client.run("export lasote/testing")
        client.save({"conanfile.py": chatconanfile_py}, clean_first=True)
        client.run("export lasote/testing")
        client.save({"conanfile.txt": conanfile.replace("Hello", "Chat"),
                     "CMakeLists.txt": cmake}, clean_first=True)

        client.run('install -g cmake')
        client.runner("cmake .", cwd=client.current_folder)
        self.assertIn("CMAKE_CXX_FLAGS=/DWIN32 /D_WINDOWS /W3 /GR /EHsc MyFlag1 MyFlag2 "
                      "MyChatFlag1 MyChatFlag2",
                      client.user_io.out)
        self.assertIn("CONAN_CXX_FLAGS=MyFlag1 MyFlag2 MyChatFlag1 MyChatFlag2",
                      client.user_io.out)

    def targets_flags_test(self):
        client = TestClient()
        client.save({"conanfile.py": conanfile_py})
        client.run("export lasote/testing")
        cmake_targets = cmake.replace("conan_basic_setup()",
                                      "conan_basic_setup(TARGETS)\n"
                                      "get_target_property(HELLO_FLAGS CONAN_PKG::Hello"
                                      " INTERFACE_COMPILE_OPTIONS)")
        client.save({"conanfile.txt": conanfile,
                     "CMakeLists.txt": cmake_targets},
                    clean_first=True)

        client.run('install -g cmake')
        client.runner("cmake .", cwd=client.current_folder)
        self.assertIn("CMAKE_CXX_FLAGS=/DWIN32 /D_WINDOWS /W3 /GR /EHsc",
                      client.user_io.out)
        self.assertIn("CONAN_CXX_FLAGS=MyFlag1 MyFlag2", client.user_io.out)
        self.assertIn("HELLO_CXX_FLAGS=MyFlag1 MyFlag2;"
                      "$<$<CONFIG:Release>:;>;$<$<CONFIG:Debug>:;>", client.user_io.out)

    def transitive_targets_flags_test(self):
        client = TestClient()
        client.save({"conanfile.py": conanfile_py})
        client.run("export lasote/testing")
        client.save({"conanfile.py": chatconanfile_py}, clean_first=True)
        client.run("export lasote/testing")
        cmake_targets = cmake.replace("conan_basic_setup()",
                                      "conan_basic_setup(TARGETS)\n"
                                      "get_target_property(HELLO_FLAGS CONAN_PKG::Hello"
                                      " INTERFACE_COMPILE_OPTIONS)\n"
                                      "get_target_property(CHAT_FLAGS CONAN_PKG::Chat"
                                      " INTERFACE_COMPILE_OPTIONS)\n")
        client.save({"conanfile.txt": conanfile.replace("Hello", "Chat"),
                     "CMakeLists.txt": cmake_targets},
                    clean_first=True)

        client.run('install -g cmake')
        client.runner("cmake .", cwd=client.current_folder)

        self.assertIn("CMAKE_CXX_FLAGS=/DWIN32 /D_WINDOWS /W3 /GR /EHsc",
                      client.user_io.out)
        self.assertIn("CONAN_CXX_FLAGS=MyFlag1 MyFlag2 MyChatFlag1 MyChatFlag2",
                      client.user_io.out)
        self.assertIn("HELLO_CXX_FLAGS=MyFlag1 MyFlag2;"
                      "$<$<CONFIG:Release>:;>;$<$<CONFIG:Debug>:;>", client.user_io.out)
        self.assertIn("CHAT_CXX_FLAGS=MyChatFlag1 MyChatFlag2;"
                      "$<$<CONFIG:Release>:;>;$<$<CONFIG:Debug>:;>", client.user_io.out)
