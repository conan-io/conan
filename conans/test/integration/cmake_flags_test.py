import platform
import unittest
import os
from nose.plugins.attrib import attr
from parameterized.parameterized import parameterized

from conans.model.version import Version
from conans.client.build.cmake import CMake
from conans.test.utils.tools import TestClient


conanfile_py = """
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"
    build_policy="missing"
    def package_info(self):
        self.cpp_info.cppflags = ["MyFlag1", "MyFlag2"]
        self.cpp_info.cflags = ["-load", "C:\some\path"]
        self.cpp_info.defines = ['MY_DEF=My" \string', 'MY_DEF2=My${} other \string']
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
message(STATUS "CMAKE_C_FLAGS=${CMAKE_C_FLAGS}")
message(STATUS "CONAN_C_FLAGS=${CONAN_C_FLAGS}")
message(STATUS "HELLO_CXX_FLAGS=${HELLO_FLAGS}")
message(STATUS "CHAT_CXX_FLAGS=${CHAT_FLAGS}")
message(STATUS "CONAN_DEFINES_HELLO=${CONAN_DEFINES_HELLO}")
message(STATUS "HELLO_DEFINES=${HELLO_DEFINES}")
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

    @parameterized.expand([(True, ), (False, )])
    def build_app_test(self, targets):
        client = TestClient()
        conanfile_py = """
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"
    def package_info(self):
        self.cpp_info.defines = [r'MY_DEF=My${} $string', r'MY_DEF2=My$ other string']
"""
        client.save({"conanfile.py": conanfile_py})
        client.run("create . lasote/testing")
        consumer = """from conans import ConanFile, CMake
import os
class App(ConanFile):
    settings = "os", "compiler", "arch", "build_type"
    requires = "Hello/0.1@lasote/testing"
    generators = "cmake"
    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()
        self.run(os.sep.join([".", "bin", "myapp"]))
"""
        cmake_app = """set(CMAKE_CXX_COMPILER_WORKS 1)
set(CMAKE_CXX_ABI_COMPILED 1)
project(MyHello CXX)
cmake_minimum_required(VERSION 2.8.12)

include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
conan_basic_setup(%s)
add_executable(myapp myapp.cpp)
conan_target_link_libraries(myapp)
""" % ("TARGETS" if targets else "")

        myapp = r"""#include <iostream>
#define STRINGIFY(x) #x
#define STRINGIFYMACRO(y) STRINGIFY(y)
int main(){
    std::cout << "Msg1: " << STRINGIFYMACRO(MY_DEF) << "\n";
    std::cout << "Msg2: " << STRINGIFYMACRO(MY_DEF2) << "\n";
}"""
        client.save({"conanfile.py": consumer,
                     "CMakeLists.txt": cmake_app,
                     "myapp.cpp": myapp
                     }, clean_first=True)
        client.run("install .")
        client.run("build .")
        self.assertIn("Msg1: My${} $string", client.out)
        self.assertIn("Msg2: My$ other string", client.out)

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
        self.assertIn("CONAN_CXX_FLAGS=MyFlag1 MyFlag2", client.out)
        self.assertIn("CMAKE_C_FLAGS= -load C:\some\path", client.out)
        self.assertIn("CONAN_C_FLAGS=-load C:\some\path ", client.out)
        self.assertIn('CONAN_DEFINES_HELLO=-DMY_DEF=My" \string;-DMY_DEF2=My${} other \string',
                      client.out)

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
                                      " INTERFACE_COMPILE_OPTIONS)\n"
                                      "get_target_property(HELLO_DEFINES CONAN_PKG::Hello"
                                      " INTERFACE_COMPILE_DEFINITIONS)")
        client.save({"conanfile.txt": conanfile,
                     "CMakeLists.txt": cmake_targets},
                    clean_first=True)

        client.run('install . -g cmake')
        client.runner("cmake .", cwd=client.current_folder)
        cmake_cxx_flags = self._get_line(client.out, "CMAKE_CXX_FLAGS")
        self.assertNotIn("My", cmake_cxx_flags)
        self.assertIn("CONAN_CXX_FLAGS=MyFlag1 MyFlag2", client.out)
        self.assertIn("HELLO_CXX_FLAGS=-load;C:\some\path;MyFlag1;MyFlag2;"
                      "$<$<CONFIG:Release>:;>;$<$<CONFIG:RelWithDebInfo>:;>;"
                      "$<$<CONFIG:MinSizeRel>:;>;$<$<CONFIG:Debug>:;>", client.out)
        self.assertIn('HELLO_DEFINES=MY_DEF=My" \string;MY_DEF2=My${} other \string;', client.out)

    def targets_own_flags_test(self):
        client = TestClient()
        client.save({"conanfile.py": conanfile_py.replace('version = "0.1"',
                                                          'version = "0.1"\n'
                                                          '    settings = "compiler"')})
        client.run("export . lasote/testing")
        cmake_targets = cmake.replace("conan_basic_setup()",
                                      "conan_basic_setup(TARGETS)\n"
                                      "get_target_property(HELLO_FLAGS CONAN_PKG::Hello"
                                      " INTERFACE_COMPILE_OPTIONS)\n"
                                      "get_target_property(HELLO_DEFINES CONAN_PKG::Hello"
                                      " INTERFACE_COMPILE_DEFINITIONS)")
        client.save({"conanfile.txt": conanfile,
                     "CMakeLists.txt": cmake_targets},
                    clean_first=True)

        client.run('install . -g cmake')
        client.runner("cmake . -DCONAN_CXX_FLAGS=CmdCXXFlag", cwd=client.current_folder)
        cmake_cxx_flags = self._get_line(client.user_io.out, "CMAKE_CXX_FLAGS")
        self.assertNotIn("My", cmake_cxx_flags)
        self.assertIn("CmdCXXFlag", cmake_cxx_flags)
        self.assertIn("CONAN_CXX_FLAGS=MyFlag1 MyFlag2 CmdCXXFlag", client.user_io.out)
        self.assertIn("HELLO_CXX_FLAGS=-load;C:\some\path;MyFlag1;MyFlag2;"
                      "$<$<CONFIG:Release>:;>;$<$<CONFIG:RelWithDebInfo>:;>;"
                      "$<$<CONFIG:MinSizeRel>:;>;$<$<CONFIG:Debug>:;>", client.out)
        self.assertIn('HELLO_DEFINES=MY_DEF=My" \string;MY_DEF2=My${} other \string;', client.out)

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
                                      " INTERFACE_COMPILE_OPTIONS)\n"
                                      "get_target_property(HELLO_DEFINES CONAN_PKG::Hello"
                                      " INTERFACE_COMPILE_DEFINITIONS)")
        client.save({"conanfile.txt": conanfile.replace("Hello", "Chat"),
                     "CMakeLists.txt": cmake_targets},
                    clean_first=True)

        client.run('install . -g cmake')
        client.runner("cmake .", cwd=client.current_folder)

        cmake_cxx_flags = self._get_line(client.user_io.out, "CMAKE_CXX_FLAGS")
        self.assertNotIn("My", cmake_cxx_flags)
        self.assertIn("CONAN_CXX_FLAGS=MyFlag1 MyFlag2 MyChatFlag1 MyChatFlag2",
                      client.user_io.out)
        self.assertIn("HELLO_CXX_FLAGS=-load;C:\some\path;MyFlag1;MyFlag2;"
                      "$<$<CONFIG:Release>:;>;$<$<CONFIG:RelWithDebInfo>:;>;"
                      "$<$<CONFIG:MinSizeRel>:;>;$<$<CONFIG:Debug>:;>", client.out)
        self.assertIn("CHAT_CXX_FLAGS=MyChatFlag1;MyChatFlag2;"
                      "$<$<CONFIG:Release>:;>;$<$<CONFIG:RelWithDebInfo>:;>;"
                      "$<$<CONFIG:MinSizeRel>:;>;$<$<CONFIG:Debug>:;>", client.out)
        self.assertIn('HELLO_DEFINES=MY_DEF=My" \string;MY_DEF2=My${} other \string;', client.out)

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
            client.run("build .")

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
        self.assertNotIn("Conan setting CXX_FLAGS flags", client.out)
        libname = "libmylib.a" if platform.system() != "Windows" else "mylib.lib"
        libpath = os.path.join(client.current_folder, "build", "lib", libname)
        self.assertTrue(os.path.exists(libpath))

    def standard_20_as_cxx_flag_test(self):
        # CMake (1-Jun-2018) do not support the 20 flag in CMAKE_CXX_STANDARD var
        conanfile = """
import os
from conans import ConanFile, CMake
class MyLib(ConanFile):
    name = "MyLib"
    version = "0.1"
    settings = "arch", "compiler", "cppstd"
    exports_sources = "CMakeLists.txt"
    generators = "cmake"

    def build(self):
        cmake = CMake(self)
        cmake.configure()
"""
        cmakelists = """
set(CMAKE_CXX_COMPILER_WORKS 1)
set(CMAKE_CXX_ABI_COMPILED 1)
project(MyHello CXX)
cmake_minimum_required(VERSION 2.8.12)
include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
conan_set_std()
"""
        client = TestClient()
        client.save({"conanfile.py": conanfile,
                     "CMakeLists.txt": cmakelists})

        def conan_set_std_branch():
            # Replicate logic from cmake_common definition of 'macro(conan_set_std)'
            cmake_version = CMake.get_version()
            return cmake_version < Version("3.12")

        client.run("create . user/channel -s cppstd=gnu20 -s compiler=gcc -s compiler.version=8 "
               "-s compiler.libcxx=libstdc++11")
        if conan_set_std_branch():
            self.assertIn("Conan setting CXX_FLAGS flags: -std=gnu++2a", client.out)
        else:
            self.assertIn("Conan setting CPP STANDARD: 20 WITH EXTENSIONS ON", client.out)

        client.run("create . user/channel -s cppstd=20 -s compiler=gcc -s compiler.version=8 "
                   "-s compiler.libcxx=libstdc++11")
        if conan_set_std_branch():
            self.assertIn("Conan setting CXX_FLAGS flags: -std=c++2a", client.out)
        else:
            self.assertIn("Conan setting CPP STANDARD: 20 WITH EXTENSIONS OFF", client.out)

    def fpic_applied_test(self):
        conanfile = """
import os
from conans import ConanFile, CMake
class MyLib(ConanFile):
    name = "MyLib"
    version = "0.1"
    settings = "arch", "compiler"
    options = {"fPIC": [True, False]}
    default_options = "fPIC=False"
    generators = "cmake"
    exports_sources = "CMakeLists.txt"

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()
"""
        cmakelists = """
set(CMAKE_CXX_COMPILER_WORKS 1)
set(CMAKE_CXX_ABI_COMPILED 1)
project(MyHello CXX)
cmake_minimum_required(VERSION 2.8.12)
include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
conan_basic_setup()
"""
        client = TestClient()
        client.save({"conanfile.py": conanfile,
                     "CMakeLists.txt": cmakelists})

        client.run("create . user/channel -o MyLib:fPIC=True")
        self.assertIn("Conan: Adjusting fPIC flag (ON)", client.out)

        client.run("create . user/channel -o MyLib:fPIC=False")
        self.assertIn("Conan: Adjusting fPIC flag (OFF)", client.out)

        client.save({"conanfile.py": conanfile.replace("fPIC", "fpic")}, clean_first=False)
        client.run("create . user/channel -o MyLib:fpic=True")
        self.assertNotIn("Conan: Adjusting fPIC flag (ON)", client.out)

        # Skip fpic adjustements in basic setup
        tmp = cmakelists.replace("conan_basic_setup()", "conan_basic_setup(SKIP_FPIC)")
        client.save({"CMakeLists.txt": tmp, "conanfile.py": conanfile}, clean_first=True)
        client.run("create . user/channel -o MyLib:fPIC=True")
        self.assertNotIn("Conan: Adjusting fPIC flag (ON)", client.out)
