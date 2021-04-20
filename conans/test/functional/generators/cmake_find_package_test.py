import os
import platform
import textwrap
import unittest

import pytest
import six

from conans.client.tools import replace_in_file
from conans.model.ref import ConanFileReference, PackageReference
from conans.test.assets.cpp_test_files import cpp_hello_conan_files
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient, NO_SETTINGS_PACKAGE_ID


@pytest.mark.tool_cmake
class TestCMakeFindPackageGenerator:

    @pytest.mark.parametrize("use_components", [False, True])
    def test_build_modules_alias_target(self, use_components):
        client = TestClient()
        conanfile = textwrap.dedent("""
            import os
            from conans import ConanFile, CMake

            class Conan(ConanFile):
                name = "hello"
                version = "1.0"
                settings = "os", "arch", "compiler", "build_type"
                exports_sources = ["target-alias.cmake"]
                generators = "cmake"

                def package(self):
                    self.copy("target-alias.cmake", dst="share/cmake")

                def package_info(self):
                    module = os.path.join("share", "cmake", "target-alias.cmake")
            %s
            """)
        if use_components:
            info = textwrap.dedent("""\
                self.cpp_info.name = "namespace"
                self.cpp_info.filenames["cmake_find_package"] = "hello"
                self.cpp_info.components["comp"].libs = ["hello"]
                self.cpp_info.components["comp"].build_modules["cmake_find_package"].append(module)
                """)
        else:
            info = textwrap.dedent("""\
                self.cpp_info.libs = ["hello"]
                self.cpp_info.build_modules["cmake_find_package"].append(module)
                """)
        target_alias = textwrap.dedent("""
            add_library(otherhello INTERFACE IMPORTED)
            target_link_libraries(otherhello INTERFACE {target_name})
            """).format(target_name="namespace::comp" if use_components else "hello::hello")
        conanfile = conanfile % "\n".join(["        %s" % line for line in info.splitlines()])
        client.save({"conanfile.py": conanfile, "target-alias.cmake": target_alias})
        client.run("create .")

        consumer = textwrap.dedent("""
            from conans import ConanFile, CMake

            class Conan(ConanFile):
                name = "consumer"
                version = "1.0"
                settings = "os", "compiler", "build_type", "arch"
                exports_sources = ["CMakeLists.txt"]
                generators = "cmake_find_package"
                requires = "hello/1.0"

                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
            """)
        cmakelists = textwrap.dedent("""
            set(CMAKE_CXX_COMPILER_WORKS 1)
            set(CMAKE_CXX_ABI_COMPILED 1)
            cmake_minimum_required(VERSION 3.0)
            project(test CXX)
            find_package(hello)
            get_target_property(tmp otherhello INTERFACE_LINK_LIBRARIES)
            message("otherhello link libraries: ${tmp}")
            """)
        client.save({"conanfile.py": consumer, "CMakeLists.txt": cmakelists})
        client.run("create .")
        if use_components:
            assert "otherhello link libraries: namespace::comp" in client.out
        else:
            assert "otherhello link libraries: hello::hello" in client.out


@pytest.mark.slow
@pytest.mark.tool_cmake
class CMakeFindPathGeneratorTest(unittest.TestCase):

    def test_cmake_find_package_system_libs(self):
        conanfile = """from conans import ConanFile, tools
class Test(ConanFile):
    name = "Test"
    version = "0.1"

    def package_info(self):
        self.cpp_info.libs.append("fake_lib")
        self.cpp_info.cflags.append("a_flag")
        self.cpp_info.cxxflags.append("a_cxx_flag")
        self.cpp_info.sharedlinkflags.append("-shared_link_flag")
    """
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("export . user/channel")

        conanfile = """from conans import ConanFile, tools, CMake
class Consumer(ConanFile):
    name = "consumer"
    version = "0.1"
    requires = "Test/0.1@user/channel"
    generators = "cmake_find_package"
    exports_sources = "CMakeLists.txt"
    settings = "os", "arch", "compiler"

    def build(self):
        cmake = CMake(self)
        cmake.configure()
    """
        cmakelists = """
set(CMAKE_CXX_COMPILER_WORKS 1)
set(CMAKE_CXX_ABI_COMPILED 1)
project(consumer CXX)
cmake_minimum_required(VERSION 3.1)
find_package(Test)
message("Libraries to Link: ${Test_LIBS}")
message("Version: ${Test_VERSION}")

get_target_property(tmp Test::Test INTERFACE_LINK_LIBRARIES)
message("Target libs: ${tmp}")

get_target_property(tmp Test::Test INTERFACE_COMPILE_OPTIONS)
message("Compile options: ${tmp}")
"""
        client.save({"conanfile.py": conanfile, "CMakeLists.txt": cmakelists})
        client.run("create . user/channel --build missing")
        self.assertIn("Library fake_lib not found in package, might be system one", client.out)
        self.assertIn("Libraries to Link: fake_lib", client.out)
        self.assertIn("Version: 0.1", client.out)
        self.assertIn("Target libs: fake_lib;;"
                      "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,SHARED_LIBRARY>:-shared_link_flag>;"
                      "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,MODULE_LIBRARY>:-shared_link_flag>;"
                      "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,EXECUTABLE>:>", client.out)
        self.assertIn("Compile options: a_cxx_flag;a_flag", client.out)

    def test_cmake_lock_target_redefinition(self):
        client = TestClient()
        files = cpp_hello_conan_files(name="Hello0",
                                      settings='"os", "compiler", "arch", "build_type"')
        client.save(files)
        client.run("create . user/channel -s build_type=Release")

        # Consume the previous Hello0 with auto generated FindHello0.cmake
        # The module path will point to the "install" folder automatically (CMake helper)
        files = cpp_hello_conan_files(name="Hello1", deps=["Hello0/0.1@user/channel"],
                                      settings='"os", "compiler", "arch", "build_type"')
        files["conanfile.py"] = files["conanfile.py"].replace(
            'generators = "cmake", "gcc"',
            'generators = "cmake_find_package"')
        files["CMakeLists.txt"] = """
set(CMAKE_CXX_COMPILER_WORKS 1)
set(CMAKE_CXX_ABI_COMPILED 1)
project(MyHello CXX)
cmake_minimum_required(VERSION 3.1)

# Add fake library
add_library(fake)
# Create an alias target to check if it is not redefined.
# Only IMPORTED and ALIAS libraries may use :: as part of the
# target name (See CMake policy CMP0037). This ALIAS target
# fakes the IMPORTED targets used in the generated FindXXXX.cmake files
add_library(CONAN_LIB::Hello0_helloHello0 ALIAS fake)

find_package(Hello0 REQUIRED)

get_target_property(tmp Hello0::Hello0 INTERFACE_LINK_LIBRARIES)
message("Target libs: ${tmp}")

"""
        client.save(files, clean_first=True)
        client.run("create . user/channel -s build_type=Release", assert_error=True)
        self.assertIn("Skipping already existing target: CONAN_LIB::Hello0_helloHello0", client.out)
        self.assertIn("Target libs: CONAN_LIB::Hello0_helloHello0", client.out)

    def test_cmake_find_dependency_redefinition(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile, CMake
            class Consumer(ConanFile):
                name = "App"
                version = "1.0"
                requires = "PkgC/1.0@user/testing"
                generators = "cmake_find_package"
                exports_sources = "CMakeLists.txt"
                settings = "os", "arch", "compiler"

                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
        """)

        cmakelists = textwrap.dedent("""
            set(CMAKE_CXX_COMPILER_WORKS 1)
            set(CMAKE_CXX_ABI_COMPILED 1)
            cmake_minimum_required(VERSION 3.0)
            project(app CXX)
            find_package(PkgC)
        """)

        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . PkgA/1.0@user/testing")
        client.save({"conanfile.py": GenConanfile().with_require("PkgA/1.0@user/testing")})
        client.run("create . PkgB/1.0@user/testing")
        client.save({"conanfile.py": GenConanfile().with_require("PkgB/1.0@user/testing")
                                                   .with_require("PkgA/1.0@user/testing")})
        client.run("create . PkgC/1.0@user/testing")
        client.save({"conanfile.py": conanfile,
                     "CMakeLists.txt": cmakelists})
        client.run("create . App/1.0@user/testing")
        self.assertIn("Dependency PkgA already found", client.out)

    def test_cmake_find_package(self):
        """First package without custom find_package"""
        client = TestClient()
        files = cpp_hello_conan_files(name="Hello0",
                                      settings='"os", "compiler", "arch", "build_type"')
        client.save(files)
        client.run("create . user/channel -s build_type=Release")

        # Consume the previous Hello0 with auto generated FindHello0.cmake
        # The module path will point to the "install" folder automatically (CMake helper)
        files = cpp_hello_conan_files(name="Hello1", deps=["Hello0/0.1@user/channel"],
                                      settings='"os", "compiler", "arch", "build_type"')
        files["conanfile.py"] = files["conanfile.py"].replace(
            'generators = "cmake", "gcc"',
            'generators = "cmake_find_package"')
        files["CMakeLists.txt"] = """
set(CMAKE_CXX_COMPILER_WORKS 1)
set(CMAKE_CXX_ABI_COMPILED 1)
project(MyHello CXX)
cmake_minimum_required(VERSION 2.8)

find_package(Hello0 REQUIRED)

add_library(helloHello1 hello.cpp)
target_link_libraries(helloHello1 PUBLIC Hello0::Hello0)
if(Hello0_LIBRARIES)
    MESSAGE("Hello0_LIBRARIES set")
endif()
message("Version: ${Hello0_VERSION}")
add_executable(say_hello main.cpp)
target_link_libraries(say_hello helloHello1)

"""
        client.save(files, clean_first=True)
        client.run("create . user/channel -s build_type=Release")
        self.assertIn("Conan: Using autogenerated FindHello0.cmake", client.out)
        self.assertIn("Hello0_LIBRARIES set", client.out)
        self.assertIn("Version: 0.1", client.out)
        self.assertNotIn("Skipping already existing target", client.out)

        # Now link with old cmake
        files["CMakeLists.txt"] = """
set(CMAKE_VERSION "2.8")
set(CMAKE_CXX_COMPILER_WORKS 1)
set(CMAKE_CXX_ABI_COMPILED 1)
project(MyHello CXX)
cmake_minimum_required(VERSION 2.8)
message(${CMAKE_BINARY_DIR})
set(CMAKE_MODULE_PATH ${CMAKE_BINARY_DIR} ${CMAKE_MODULE_PATH})

find_package(Hello0 REQUIRED)

add_library(helloHello1 hello.cpp)

if(NOT DEFINED Hello0_FOUND)
    message(FATAL_ERROR "Hello0_FOUND not declared")
endif()
if(NOT DEFINED Hello0_INCLUDE_DIRS)
    message(FATAL_ERROR "Hello0_INCLUDE_DIRS not declared")
endif()
if(NOT DEFINED Hello0_INCLUDE_DIR)
    message(FATAL_ERROR "Hello0_INCLUDE_DIR not declared")
endif()
if(NOT DEFINED Hello0_INCLUDES)
    message(FATAL_ERROR "Hello0_INCLUDES not declared")
endif()
if(NOT DEFINED Hello0_LIBRARIES)
    message(FATAL_ERROR "Hello0_LIBRARIES not declared")
endif()

include_directories(${Hello0_INCLUDE_DIRS})
target_link_libraries(helloHello1 PUBLIC ${Hello0_LIBS})
add_executable(say_hello main.cpp)
target_link_libraries(say_hello helloHello1)
"""
        client.save(files, clean_first=True)
        client.run("create . user/channel -s build_type=Release")
        self.assertIn("Conan: Using autogenerated FindHello0.cmake", client.out)

        # Now a transitive consumer, but the consumer only find_package the first level Hello1
        files = cpp_hello_conan_files(name="Hello2", version="0.2", deps=["Hello1/0.1@user/channel"],
                                      settings='"os", "compiler", "arch", "build_type"')
        files["CMakeLists.txt"] = """
set(CMAKE_CXX_COMPILER_WORKS 1)
set(CMAKE_CXX_ABI_COMPILED 1)
project(MyHello CXX)
cmake_minimum_required(VERSION 2.8)
set(CMAKE_MODULE_PATH ${CMAKE_BINARY_DIR} ${CMAKE_MODULE_PATH})
find_package(Hello1 REQUIRED) # We don't need to find Hello0, it is transitive
message("Version1: ${Hello1_VERSION}")

add_library(helloHello2 hello.cpp)
target_link_libraries(helloHello2 PUBLIC Hello1::Hello1)

add_executable(say_hello main.cpp)
target_link_libraries(say_hello helloHello2)
        """
        files["conanfile.py"] = files["conanfile.py"].replace(
            'generators = "cmake", "gcc"',
            'generators = "cmake_find_package"')
        client.save(files, clean_first=True)
        client.run("create . user/channel -s build_type=Release")
        self.assertIn("Conan: Using autogenerated FindHello0.cmake", client.out)
        self.assertIn("Conan: Using autogenerated FindHello1.cmake", client.out)
        self.assertIn("Version1: 0.1", client.out)

    def test_cmake_find_package_cpp_info_system_libs(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile, tools

            class Test(ConanFile):
                name = "Test"
                version = "0.1"

                def package_info(self):
                    self.cpp_info.libs = ["lib1"]
                    self.cpp_info.system_libs = ["sys1"]
        """)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("export .")

        conanfile = textwrap.dedent("""
            from conans import ConanFile, CMake

            class Consumer(ConanFile):
                name = "consumer"
                version = "0.1"
                requires = "Test/0.1"
                generators = "cmake_find_package"
                exports_sources = "CMakeLists.txt"
                settings = "os", "arch", "compiler"

                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
        """)
        cmakelists = textwrap.dedent("""
            set(CMAKE_CXX_COMPILER_WORKS 1)
            set(CMAKE_CXX_ABI_COMPILED 1)
            cmake_minimum_required(VERSION 3.1)
            project(consumer CXX)
            find_package(Test)
            message("Package libs: ${Test_LIBS}")
            message("Package version: ${Test_VERSION}")
            message("System deps: ${Test_SYSTEM_LIBS}")
            get_target_property(tmp Test::Test INTERFACE_LINK_LIBRARIES)
            message("Target linked libs: ${tmp}")
        """)
        client.save({"conanfile.py": conanfile, "CMakeLists.txt": cmakelists})
        client.run("create . user/channel --build missing")
        self.assertIn("Package libs: lib1", client.out)
        self.assertIn("Package version: 0.1", client.out)
        self.assertIn("System deps: sys1", client.out)
        self.assertNotIn("-- Library sys1 not found in package, might be system one", client.out)
        self.assertIn("Target linked libs: lib1;sys1;;", client.out)

    @pytest.mark.skipif(platform.system() != "Darwin", reason="Requires Apple Frameworks")
    def test_cmake_find_package_frameworks(self):
        conanfile = """from conans import ConanFile, tools
class Test(ConanFile):
    name = "Test"
    version = "0.1"

    def package_info(self):
        self.cpp_info.frameworks.append("Foundation")
    """
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("export . user/channel")

        conanfile = """from conans import ConanFile, tools, CMake
class Consumer(ConanFile):
    name = "consumer"
    version = "0.1"
    requires = "Test/0.1@user/channel"
    generators = "cmake_find_package"
    exports_sources = "CMakeLists.txt"
    settings = "os", "arch", "compiler"

    def build(self):
        cmake = CMake(self)
        cmake.configure()
    """
        cmakelists = """
set(CMAKE_CXX_COMPILER_WORKS 1)
set(CMAKE_CXX_ABI_COMPILED 1)
project(consumer CXX)
cmake_minimum_required(VERSION 3.1)
find_package(Test)
message("Libraries to link: ${Test_LIBS}")
message("Version: ${Test_VERSION}")
message("Frameworks: ${Test_FRAMEWORKS}")
message("Frameworks found: ${Test_FRAMEWORKS_FOUND}")

get_target_property(tmp Test::Test INTERFACE_LINK_LIBRARIES)
message("Target libs: ${tmp}")
"""
        client.save({"conanfile.py": conanfile, "CMakeLists.txt": cmakelists})
        client.run("create . user/channel --build missing")
        self.assertIn("Libraries to link:", client.out)
        self.assertIn('Found Test: 0.1 (found version "0.1")', client.out)
        self.assertIn("Version: 0.1", client.out)
        self.assertIn("Frameworks: Foundation", client.out)
        six.assertRegex(self, str(client.out),
                        r"Frameworks found: [^\s]*/System/Library/Frameworks/Foundation.framework")
        six.assertRegex(self, str(client.out),
                        r"Target libs: [^\s]*/System/Library/Frameworks/Foundation.framework;;")

        self.assertNotIn("Foundation.framework not found in package, might be system one",
                         client.out)
        if six.PY2:
            self.assertNotRegexpMatches(str(client.out),
                                        r"Libraries to link: .*Foundation\.framework")
        else:
            self.assertNotRegex(str(client.out), r"Libraries to link: .*Foundation\.framework")

    def test_build_modules(self):
        conanfile = textwrap.dedent("""
            import os
            from conans import ConanFile, CMake

            class Conan(ConanFile):
                name = "test"
                version = "1.0"
                exports_sources = ["my-module.cmake", "FindFindModule.cmake"]

                def package(self):
                    self.copy("*.cmake", dst="share/cmake")

                def package_info(self):
                    # Only first module is defined
                    # (the other one should be found by CMAKE_MODULE_PATH in builddirs)
                    builddir = os.path.join("share", "cmake")
                    module = os.path.join(builddir, "my-module.cmake")
                    self.cpp_info.build_modules.append(module)
                    self.cpp_info.builddirs = [builddir]
        """)
        # This is a module that has other find_package() calls
        my_module = textwrap.dedent("""
            find_package(FindModule REQUIRED)
            """)
        # This is a module that defines some functionality
        find_module = textwrap.dedent("""
            function(custom_message MESSAGE_OUTPUT)
                message(${ARGV${0}})
            endfunction()
            """)
        client = TestClient()
        client.save({"conanfile.py": conanfile, "my-module.cmake": my_module,
                     "FindFindModule.cmake": find_module})
        client.run("create .")
        ref = ConanFileReference("test", "1.0", None, None)
        pref = PackageReference(ref, NO_SETTINGS_PACKAGE_ID, None)
        package_path = client.cache.package_layout(ref).package(pref)
        modules_path = os.path.join(package_path, "share", "cmake")
        self.assertEqual(set(os.listdir(modules_path)), {"FindFindModule.cmake", "my-module.cmake"})

        consumer = textwrap.dedent("""
            from conans import ConanFile, CMake

            class Conan(ConanFile):
                name = "consumer"
                version = "1.0"
                settings = "os", "compiler", "build_type", "arch"
                exports_sources = ["CMakeLists.txt"]
                generators = "cmake_find_package"
                requires = "test/1.0"

                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
                    cmake.build()
            """)
        cmakelists = textwrap.dedent("""
            set(CMAKE_CXX_COMPILER_WORKS 1)
            set(CMAKE_CXX_ABI_COMPILED 1)
            cmake_minimum_required(VERSION 3.0)
            project(test CXX)
            find_package(test)
            custom_message("Printing using a external module!")
            """)
        client.save({"conanfile.py": consumer, "CMakeLists.txt": cmakelists})
        client.run("create .")
        self.assertIn("Printing using a external module!", client.out)

    def test_cpp_info_name(self):
        client = TestClient()
        client.run("new hello/1.0 -s")
        replace_in_file(os.path.join(client.current_folder, "conanfile.py"),
                        'self.cpp_info.libs = ["hello"]',
                        'self.cpp_info.libs = ["hello"]\n        self.cpp_info.name = "MYHELLO"',
                        output=client.out)
        client.run("create .")
        client.run("new hello2/1.0 -s")
        replace_in_file(os.path.join(client.current_folder, "conanfile.py"),
                        'self.cpp_info.libs = ["hello2"]',
                        'self.cpp_info.libs = ["hello2"]\n        self.cpp_info.name = "MYHELLO2"',
                        output=client.out)
        replace_in_file(os.path.join(client.current_folder, "conanfile.py"),
                        'exports_sources = "src/*"',
                        'exports_sources = "src/*"\n    requires = "hello/1.0"',
                        output=client.out)
        client.run("create .")
        cmakelists = textwrap.dedent("""
            set(CMAKE_CXX_ABI_COMPILED 1)
            set(CMAKE_CXX_COMPILER_WORKS 1)
            project(consumer CXX)
            cmake_minimum_required(VERSION 3.1)
            find_package(MYHELLO2)

            get_target_property(tmp MYHELLO2::MYHELLO2 INTERFACE_LINK_LIBRARIES)
            message("Target libs (hello2): ${tmp}")

            get_target_property(tmp MYHELLO::MYHELLO INTERFACE_LINK_LIBRARIES)
            message("Target libs (hello): ${tmp}")
            """)
        conanfile = textwrap.dedent("""
            from conans import ConanFile, CMake

            class Conan(ConanFile):
                requires = "hello2/1.0"
                generators = "cmake_find_package"

                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
            """)
        client.save({"conanfile.py": conanfile, "CMakeLists.txt": cmakelists})
        client.run("install .")
        client.run("build .")
        self.assertIn('Found MYHELLO2: 1.0 (found version "1.0")', client.out)
        self.assertIn('Found MYHELLO: 1.0 (found version "1.0")', client.out)
        self.assertIn("Target libs (hello2): "
                      "CONAN_LIB::MYHELLO2_hello2;MYHELLO::MYHELLO;"
                      "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,SHARED_LIBRARY>:>;"
                      "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,MODULE_LIBRARY>:>;"
                      "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,EXECUTABLE>:>",
                      client.out)
        self.assertIn("Target libs (hello): CONAN_LIB::MYHELLO_hello;;"
                      "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,SHARED_LIBRARY>:>;"
                      "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,MODULE_LIBRARY>:>;"
                      "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,EXECUTABLE>:>",
                      client.out)

    def test_cpp_info_filename(self):
        client = TestClient()
        client.run("new hello/1.0 -s")
        indent = '\n        '
        replace_in_file(
            os.path.join(client.current_folder, "conanfile.py"),
            search='self.cpp_info.libs = ["hello"]',
            replace=indent.join([
                'self.cpp_info.name = "MYHELLO"',
                'self.cpp_info.filenames["cmake_find_package"] = "hello_1"',
                'self.cpp_info.components["1"].names["cmake_find_package"] = "HELLO1"',
                'self.cpp_info.components["1"].libs = [ "hello" ]'
            ]),
            output=client.out
        )
        client.run("create .")

        client.run("new hello2/1.0 -s")
        replace_in_file(
            os.path.join(client.current_folder, "conanfile.py"),
            search='self.cpp_info.libs = ["hello2"]',
            replace=indent.join([
                'self.cpp_info.name = "MYHELLO2"',
                'self.cpp_info.filenames["cmake_find_package"] = "hello_2"',
                'self.cpp_info.components["2"].names["cmake_find_package"] = "HELLO2"',
                'self.cpp_info.components["2"].libs = [ "hello2" ]',
                'self.cpp_info.components["2"].requires = [ "hello::1"]',
            ]),
            output=client.out
        )
        replace_in_file(
            os.path.join(client.current_folder, "conanfile.py"),
            search='exports_sources = "src/*"',
            replace='exports_sources = "src/*"\n    requires = "hello/1.0"',
            output=client.out
        )
        client.run("create .")

        cmakelists = textwrap.dedent("""
            set(CMAKE_CXX_ABI_COMPILED 1)
            set(CMAKE_CXX_COMPILER_WORKS 1)
            project(consumer CXX)
            cmake_minimum_required(VERSION 3.1)
            find_package(hello_2)

            get_target_property(tmp MYHELLO2::HELLO2 INTERFACE_LINK_LIBRARIES)
            message("Target libs (hello2): ${tmp}")

            get_target_property(tmp MYHELLO::HELLO1 INTERFACE_LINK_LIBRARIES)
            message("Target libs (hello): ${tmp}")
            """)
        conanfile = textwrap.dedent("""
            from conans import ConanFile, CMake

            class Conan(ConanFile):
                requires = "hello2/1.0"
                generators = "cmake_find_package"

                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
            """)
        client.save({"conanfile.py": conanfile, "CMakeLists.txt": cmakelists})
        client.run("install .")
        client.run("build .")

        self.assertIn('Found hello_2: 1.0 (found version "1.0")', client.out)
        self.assertIn('Found hello_1: 1.0 (found version "1.0")', client.out)
        self.assertIn("Target libs (hello2): "
                      "CONAN_LIB::MYHELLO2_HELLO2_hello2;MYHELLO::HELLO1;"
                      "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,SHARED_LIBRARY>:>;"
                      "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,MODULE_LIBRARY>:>;"
                      "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,EXECUTABLE>:>",
                      client.out)
        self.assertIn("Target libs (hello): CONAN_LIB::MYHELLO_HELLO1_hello;"
                      "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,SHARED_LIBRARY>:>;"
                      "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,MODULE_LIBRARY>:>;"
                      "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,EXECUTABLE>:>",
                      client.out)

    def test_cpp_info_config(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class Requirement(ConanFile):
                name = "requirement"
                version = "version"

                settings = "os", "arch", "compiler", "build_type"

                def package_info(self):
                    self.cpp_info.libs = ["lib_both"]
                    self.cpp_info.debug.libs = ["lib_debug"]
                    self.cpp_info.release.libs = ["lib_release"]

                    self.cpp_info.cxxflags = ["-req_both"]
                    self.cpp_info.debug.cxxflags = ["-req_debug"]
                    self.cpp_info.release.cxxflags = ["-req_release"]
        """)
        t = TestClient()
        t.save({"conanfile.py": conanfile})
        t.run("create . -s build_type=Release")
        t.run("create . -s build_type=Debug")

        # Check release
        t.run("install requirement/version@ -g cmake_find_package -s build_type=Release")
        content = t.load("Findrequirement.cmake")
        self.assertIn('set(requirement_COMPILE_OPTIONS_LIST "-req_both;-req_release" "")', content)
        self.assertIn('set(requirement_LIBRARY_LIST lib_both lib_release)', content)

        # Check debug
        t.run("install requirement/version@ -g cmake_find_package -s build_type=Debug")
        content = t.load("Findrequirement.cmake")
        self.assertIn('set(requirement_COMPILE_OPTIONS_LIST "-req_both;-req_debug" "")', content)
        self.assertIn('set(requirement_LIBRARY_LIST lib_both lib_debug)', content)

    def test_components_system_libs(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class Requirement(ConanFile):
                name = "requirement"
                version = "system"

                settings = "os", "arch", "compiler", "build_type"

                def package_info(self):
                    self.cpp_info.components["component"].system_libs = ["system_lib_component"]
        """)
        t = TestClient()
        t.save({"conanfile.py": conanfile})
        t.run("create .")

        conanfile = textwrap.dedent("""
            from conans import ConanFile, tools, CMake
            class Consumer(ConanFile):
                name = "consumer"
                version = "0.1"
                requires = "requirement/system"
                generators = "cmake_find_package"
                exports_sources = "CMakeLists.txt"
                settings = "os", "arch", "compiler"

                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
        """)

        cmakelists = textwrap.dedent("""
            set(CMAKE_CXX_COMPILER_WORKS 1)
            set(CMAKE_CXX_ABI_COMPILED 1)
            project(consumer CXX)
            cmake_minimum_required(VERSION 3.1)
            find_package(requirement)
            get_target_property(tmp requirement::component INTERFACE_LINK_LIBRARIES)
            message("component libs: ${tmp}")
        """)

        t.save({"conanfile.py": conanfile, "CMakeLists.txt": cmakelists})
        t.run("create . --build missing")

        self.assertIn("component libs: system_lib_component;", t.out)
