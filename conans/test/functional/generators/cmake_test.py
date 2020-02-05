import os
import platform
import textwrap
import unittest

from nose.plugins.attrib import attr

from conans.client.tools import replace_in_file
from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient, GenConanfile, TurboTestClient


class CMakeGeneratorTest(unittest.TestCase):

    def test_no_check_compiler(self):
        # https://github.com/conan-io/conan/issues/4268
        file_content = '''from conans import ConanFile, CMake

class ConanFileToolsTest(ConanFile):
    generators = "cmake"

    def build(self):
        cmake = CMake(self)
        cmake.configure()
    '''

        cmakelists = '''cmake_minimum_required(VERSION 2.8)
PROJECT(conanzlib LANGUAGES NONE)
set(CONAN_DISABLE_CHECK_COMPILER TRUE)

include(conanbuildinfo.cmake)
CONAN_BASIC_SETUP()
'''
        client = TestClient()
        client.save({"conanfile.py": file_content,
                     "CMakeLists.txt": cmakelists})

        client.run('install .')
        client.run('build .')

    @attr("slow")
    @unittest.skipUnless(platform.system() == "Windows", "Requires MSBuild")
    def skip_check_if_toolset_test(self):
        file_content = '''from conans import ConanFile, CMake

class ConanFileToolsTest(ConanFile):
    generators = "cmake"
    exports_sources = "CMakeLists.txt"
    settings = "os", "arch", "compiler"

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()
    '''
        client = TestClient()
        cmakelists = '''
set(CMAKE_CXX_COMPILER_WORKS 1)
set(CMAKE_CXX_ABI_COMPILED 1)
PROJECT(Hello)
cmake_minimum_required(VERSION 2.8)
include("${CMAKE_BINARY_DIR}/conanbuildinfo.cmake")
CONAN_BASIC_SETUP()
'''
        client.save({"conanfile.py": file_content,
                     "CMakeLists.txt": cmakelists})
        client.run("create . lib/1.0@user/channel -s compiler='Visual Studio' -s compiler.toolset=v140")
        self.assertIn("Conan: Skipping compiler check: Declared 'compiler.toolset'", client.out)


    @attr('slow')
    def no_output_test(self):
        client = TestClient()
        client.run("new Test/1.0 --sources")
        cmakelists_path = os.path.join(client.current_folder, "src", "CMakeLists.txt")

        # Test output works as expected
        client.run("install .")
        # No need to do a full create, the build --configure is good
        client.run("build . --configure")
        self.assertIn("Conan: Using cmake global configuration", client.out)
        self.assertIn("Conan: Adjusting default RPATHs Conan policies", client.out)
        self.assertIn("Conan: Adjusting language standard", client.out)

        # Silence output
        replace_in_file(cmakelists_path,
                        "conan_basic_setup()",
                        "set(CONAN_CMAKE_SILENT_OUTPUT True)\nconan_basic_setup()",
                        output=client.out)
        client.run("build . --configure")
        self.assertNotIn("Conan: Using cmake global configuration", client.out)
        self.assertNotIn("Conan: Adjusting default RPATHs Conan policies", client.out)
        self.assertNotIn("Conan: Adjusting language standard", client.out)

        # Use TARGETS
        replace_in_file(cmakelists_path, "conan_basic_setup()", "conan_basic_setup(TARGETS)",
                        output=client.out)
        client.run("build . --configure")
        self.assertNotIn("Conan: Using cmake targets configuration", client.out)
        self.assertNotIn("Conan: Adjusting default RPATHs Conan policies", client.out)
        self.assertNotIn("Conan: Adjusting language standard", client.out)

    def system_libs_test(self):
        mylib = textwrap.dedent("""
            import os
            from conans import ConanFile

            class MyLib(ConanFile):
                settings = "os", "compiler", "arch", "build_type"
                exports_sources = "*"

                def package(self):
                    self.copy("*", dst="lib")

                def package_info(self):
                    self.cpp_info.system_libs = ["sys1"]
                    self.cpp_info.libs = ["lib1"]
                """)
        consumer = textwrap.dedent("""
            import os
            from conans import ConanFile

            class Consumer(ConanFile):
                requires = "mylib/1.0@us/ch"
                generators = "cmake"
                """)
        cmakelists = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.1)
            project(consumer CXX)
            include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
            conan_basic_setup(TARGETS)
            get_target_property(tmp CONAN_PKG::mylib INTERFACE_LINK_LIBRARIES)
            message("Target libs: ${tmp}")
            get_target_property(tmpp CONAN_LIB::mylib_lib1 INTERFACE_LINK_LIBRARIES)
            message("CONAN_LIB::mylib_lib1 system libs: ${tmpp}")
            """)
        client = TestClient()
        client.save({"conanfile_mylib.py": mylib, "conanfile_consumer.py": consumer,
                     "CMakeLists.txt": cmakelists, "lib1.lib": "", "liblib1.a": ""})
        client.run("create conanfile_mylib.py mylib/1.0@us/ch")
        client.run("install conanfile_consumer.py")

        content = client.load("conanbuildinfo.cmake")
        self.assertIn("set(CONAN_LIBS ${CONAN_LIBS} ${CONAN_SYSTEM_LIBS} ${CONAN_FRAMEWORKS_FOUND})",
                      content)
        self.assertIn("set(CONAN_LIBS_MYLIB ${CONAN_PKG_LIBS_MYLIB} ${CONAN_SYSTEM_LIBS_MYLIB} ${CONAN_FRAMEWORKS_FOUND_MYLIB})",
                      content)
        self.assertIn("set(CONAN_PKG_LIBS_MYLIB lib1)", content)
        self.assertIn("set(CONAN_SYSTEM_LIBS sys1 ${CONAN_SYSTEM_LIBS})", content)
        self.assertIn("set(CONAN_SYSTEM_LIBS_MYLIB sys1)", content)

        # Check target has libraries and system deps available
        client.run_command("cmake .")
        self.assertIn("Target libs: CONAN_LIB::mylib_lib1;sys1;$", client.out)
        self.assertIn("CONAN_LIB::mylib_lib1 system libs: ;sys1;;", client.out)

    def targets_system_libs_test(self):
        mylib = GenConanfile().with_package_info(cpp_info={"libs": ["lib1", "lib11"],
                                                           "system_libs": ["sys1"]},
                                                 env_info={})\
            .with_package_file("lib/lib1.lib", " ").with_package_file("lib/liblib1.a", " ")\
            .with_package_file("lib/lib11.lib", " ").with_package_file("lib/liblib11.a", " ")
        mylib_ref = ConanFileReference("mylib", "1.0", "us", "ch")

        myotherlib = GenConanfile().with_package_info(cpp_info={"libs": ["lib2"],
                                                                "system_libs": ["sys2"]},
                                                      env_info={}).with_require(mylib_ref) \
            .with_package_file("lib/lib2.lib", " ").with_package_file("lib/liblib2.a", " ")
        myotherlib_ref = ConanFileReference("myotherlib", "1.0", "us", "ch")

        client = TurboTestClient()
        client.create(mylib_ref, mylib)
        client.create(myotherlib_ref, myotherlib)

        consumer = textwrap.dedent("""
                    import os
                    from conans import ConanFile, CMake

                    class Consumer(ConanFile):
                        requires = "myotherlib/1.0@us/ch"
                        generators = "cmake"
                        settings = "os", "compiler", "arch", "build_type"
                        exports_sources = ["CMakeLists.txt"]

                        def build(self):
                            cmake = CMake(self)
                            cmake.configure()
                            cmake.build()
                        """)
        cmakelists = textwrap.dedent("""
                    cmake_minimum_required(VERSION 3.1)
                    project(consumer CXX)
                    include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
                    conan_basic_setup("TARGETS")

                    get_target_property(ml_pkg_libs CONAN_PKG::mylib INTERFACE_LINK_LIBRARIES)
                    message("CONAN_PKG::mylib libs: ${ml_pkg_libs}")
                    get_target_property(ml_lib1_libs CONAN_LIB::mylib_lib1 INTERFACE_LINK_LIBRARIES)
                    message("CONAN_LIB::mylib_lib1 libs: ${ml_lib1_libs}")
                    get_target_property(ml_lib11_libs CONAN_LIB::mylib_lib11 INTERFACE_LINK_LIBRARIES)
                    message("CONAN_LIB::mylib_lib11 libs: ${ml_lib11_libs}")

                    get_target_property(mol_pkg_libs CONAN_PKG::myotherlib INTERFACE_LINK_LIBRARIES)
                    message("CONAN_PKG::myotherlib libs: ${mol_pkg_libs}")
                    get_target_property(ml_lib2_libs CONAN_LIB::myotherlib_lib2 INTERFACE_LINK_LIBRARIES)
                    message("CONAN_LIB::myotherlib_lib2 libs: ${ml_lib2_libs}")
                    """)

        client.save({"conanfile.py": consumer, "CMakeLists.txt": cmakelists})
        client.run("create conanfile.py consumer/1.0@us/ch")

        self.assertNotIn("Library sys1 not found in package, might be system one", client.out)
        self.assertIn("CONAN_PKG::mylib libs: "
                      "CONAN_LIB::mylib_lib1;CONAN_LIB::mylib_lib11;sys1;$<$<CONFIG:Release>:;>;"
                      "$<$<CONFIG:RelWithDebInfo>:;>;$<$<CONFIG:MinSizeRel>:;>;$<$<CONFIG:Debug>:;>",
                      client.out)
        self.assertIn("CONAN_LIB::mylib_lib1 libs: ;sys1;;", client.out)
        self.assertIn("CONAN_LIB::mylib_lib11 libs: ;sys1;;", client.out)

        self.assertNotIn("Library sys2 not found in package, might be system one", client.out)
        self.assertIn("CONAN_PKG::myotherlib libs: "
                      "CONAN_LIB::myotherlib_lib2;sys2;CONAN_PKG::mylib;$<$<CONFIG:Release>:;CONAN_PKG::mylib;>;"
                      "$<$<CONFIG:RelWithDebInfo>:;CONAN_PKG::mylib;>;$<$<CONFIG:MinSizeRel>:;CONAN_PKG::mylib;>;"
                      "$<$<CONFIG:Debug>:;CONAN_PKG::mylib;>",
                      client.out)
        self.assertIn("CONAN_LIB::myotherlib_lib2 libs: ;sys2;;CONAN_PKG::mylib", client.out)

    def user_appended_libs_test(self):
        conanfile = textwrap.dedent("""
            import os
            from conans import ConanFile, CMake

            class MyLib(ConanFile):
                name = "mylib"
                version = "1.0"
                settings = "os", "compiler", "arch", "build_type"
                exports_sources = "lib1.a", "lib1.lib"

                def package(self):
                    self.copy("*", dst="lib")

                def package_info(self):
                    self.cpp_info.system_libs = ["sys1"]
                    self.cpp_info.libs = ["lib1"]
                """)
        consumer = textwrap.dedent("""
            import os
            from conans import ConanFile, CMake

            class Consumer(ConanFile):
                name = "consumer"
                version = "1.0"
                generators = "cmake"
                settings = "os", "compiler", "arch", "build_type"
                exports_sources = "CMakeLists.txt"
                requires = "mylib/1.0"

                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
                """)
        cmakelists = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.1)
            project(consumer CXX)
            set(CONAN_LIBS additional_lib)
            set(CONAN_SYSTEM_LIBS additional_sys)
            include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
            message("CONAN_LIBS: ${CONAN_LIBS}")
            message("CONAN_SYSTEM_LIBS: ${CONAN_SYSTEM_LIBS}")
            """)
        client = TestClient()
        client.save({"conanfile.py": conanfile, "lib1.lib": "", "liblib1.a": "",
                     "consumer.py": consumer, "CMakeLists.txt": cmakelists})
        client.run("create .")
        client.run("create consumer.py")
        self.assertIn("CONAN_LIBS: lib1;additional_lib;sys1;additional_sys", client.out)
        self.assertIn("CONAN_SYSTEM_LIBS: sys1;additional_sys", client.out)
