import os
import platform
import textwrap
import unittest

import pytest

from conans.client.tools import replace_in_file
from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient, GenConanfile, TurboTestClient


@pytest.mark.tool_cmake
class CMakeGeneratorTest(unittest.TestCase):

    def test_no_check_compiler(self):
        # https://github.com/conan-io/conan/issues/4268
        file_content = textwrap.dedent("""
            from conans import ConanFile, CMake

            class ConanFileToolsTest(ConanFile):
                generators = "cmake"

                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
                """)

        cmakelists = textwrap.dedent("""
            cmake_minimum_required(VERSION 2.8)
            PROJECT(conanzlib LANGUAGES NONE)
            set(CONAN_DISABLE_CHECK_COMPILER TRUE)

            include(conanbuildinfo.cmake)
            CONAN_BASIC_SETUP()
            """)
        client = TestClient()
        client.save({"conanfile.py": file_content,
                     "CMakeLists.txt": cmakelists})

        client.run('install .')
        client.run('build .')
        self.assertIn("WARN: Disabled conan compiler checks", client.out)

    @pytest.mark.skipif(platform.system() != "Linux", reason="Only linux")
    def test_check_compiler_package_id(self):
        # https://github.com/conan-io/conan/issues/6658
        file_content = textwrap.dedent("""
            from conans import ConanFile, CMake

            class ConanFileToolsTest(ConanFile):
                settings = "os", "compiler", "arch", "build_type"
                generators = "cmake"
                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
                def package_id(self):
                    self.info.settings.compiler.version = "SomeVersion"
                """)

        cmakelists = textwrap.dedent("""
            cmake_minimum_required(VERSION 2.8)
            project(conanzlib)
            include(conanbuildinfo.cmake)
            conan_basic_setup()
            """)
        client = TestClient()
        client.save({"conanfile.py": file_content,
                     "CMakeLists.txt": cmakelists})

        client.run('install .')
        client.run_command('cmake .')
        self.assertIn("Conan: Checking correct version:", client.out)

    @pytest.mark.slow
    @pytest.mark.tool_visual_studio
    @pytest.mark.skipif(platform.system() != "Windows", reason="Requires MSBuild")
    def test_skip_check_if_toolset(self):
        file_content = textwrap.dedent("""
            from conans import ConanFile, CMake

            class ConanFileToolsTest(ConanFile):
                generators = "cmake"
                exports_sources = "CMakeLists.txt"
                settings = "os", "arch", "compiler"

                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
                    cmake.build()
                """)
        client = TestClient()
        cmakelists = textwrap.dedent("""
            set(CMAKE_CXX_COMPILER_WORKS 1)
            set(CMAKE_CXX_ABI_COMPILED 1)
            PROJECT(Hello)
            cmake_minimum_required(VERSION 2.8)
            include("${CMAKE_BINARY_DIR}/conanbuildinfo.cmake")
            CONAN_BASIC_SETUP()
            """)
        client.save({"conanfile.py": file_content,
                     "CMakeLists.txt": cmakelists})
        client.run("create . lib/1.0@ -s compiler='Visual Studio' -s compiler.toolset=v140")
        self.assertIn("Conan: Skipping compiler check: Declared 'compiler.toolset'", client.out)

    @pytest.mark.slow
    @pytest.mark.tool_visual_studio(version="17")
    @pytest.mark.skipif(platform.system() != "Windows", reason="Requires Visual Studio")
    def test_check_msvc_compiler(self):
        """
        Checking if MSVC 19.X compiler is being called via CMake
        while using compiler=msvc in Conan profile.

        Issue related: https://github.com/conan-io/conan/issues/10185
        """
        file_content = textwrap.dedent("""
            from conans import ConanFile, CMake

            class ConanFileMSVCTest(ConanFile):
                generators = "cmake"
                exports_sources = "CMakeLists.txt"
                settings = "os", "arch", "compiler"

                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
                    cmake.build()
                """)
        client = TestClient()
        cmakelists = textwrap.dedent("""
            PROJECT(Hello)
            cmake_minimum_required(VERSION 2.8)
            include("${CMAKE_BINARY_DIR}/conanbuildinfo.cmake")
            CONAN_BASIC_SETUP()
            """)
        client.save({"conanfile.py": file_content,
                     "CMakeLists.txt": cmakelists})
        client.run("create . lib/1.0@ -s compiler=msvc -s compiler.version=193")
        self.assertIn("-- The C compiler identification is MSVC 19.3", client.out)
        self.assertIn("-- The CXX compiler identification is MSVC 19.3", client.out)

    @pytest.mark.slow
    def test_no_output(self):
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

    def test_system_libs(self):
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
        self.assertIn("set(CONAN_LIBS_MYLIB ${CONAN_PKG_LIBS_MYLIB} "
                      "${CONAN_SYSTEM_LIBS_MYLIB} ${CONAN_FRAMEWORKS_FOUND_MYLIB})",
                      content)
        self.assertIn("set(CONAN_PKG_LIBS_MYLIB lib1)", content)
        self.assertIn("set(CONAN_SYSTEM_LIBS sys1 ${CONAN_SYSTEM_LIBS})", content)
        self.assertIn("set(CONAN_SYSTEM_LIBS_MYLIB sys1)", content)

        # Check target has libraries and system deps available
        client.run_command("cmake .")
        self.assertIn("Target libs: CONAN_LIB::mylib_lib1;sys1;$", client.out)
        self.assertIn("CONAN_LIB::mylib_lib1 system libs: ;sys1;;", client.out)

    def test_targets_system_libs(self):
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
                      "CONAN_LIB::mylib_lib1;CONAN_LIB::mylib_lib11;sys1;"
                      "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,SHARED_LIBRARY>:>;"
                      "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,MODULE_LIBRARY>:>;"
                      "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,EXECUTABLE>:>;"
                      "$<$<CONFIG:Release>:;"
                      "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,SHARED_LIBRARY>:>;"
                      "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,MODULE_LIBRARY>:>;"
                      "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,EXECUTABLE>:>>;"
                      "$<$<CONFIG:RelWithDebInfo>:;"
                      "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,SHARED_LIBRARY>:>;"
                      "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,MODULE_LIBRARY>:>;"
                      "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,EXECUTABLE>:>>;"
                      "$<$<CONFIG:MinSizeRel>:;"
                      "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,SHARED_LIBRARY>:>;"
                      "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,MODULE_LIBRARY>:>;"
                      "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,EXECUTABLE>:>>;"
                      "$<$<CONFIG:Debug>:;"
                      "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,SHARED_LIBRARY>:>;"
                      "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,MODULE_LIBRARY>:>;"
                      "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,EXECUTABLE>:>>",
                      client.out)
        self.assertIn("CONAN_LIB::mylib_lib1 libs: ;sys1;;", client.out)
        self.assertIn("CONAN_LIB::mylib_lib11 libs: ;sys1;;", client.out)

        self.assertNotIn("Library sys2 not found in package, might be system one", client.out)
        self.assertIn("CONAN_PKG::myotherlib libs: "
                      "CONAN_LIB::myotherlib_lib2;sys2;CONAN_PKG::mylib;"
                      "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,SHARED_LIBRARY>:>;"
                      "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,MODULE_LIBRARY>:>;"
                      "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,EXECUTABLE>:>;"
                      "$<$<CONFIG:Release>:;CONAN_PKG::mylib;"
                      "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,SHARED_LIBRARY>:>;"
                      "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,MODULE_LIBRARY>:>;"
                      "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,EXECUTABLE>:>>;"
                      "$<$<CONFIG:RelWithDebInfo>:;CONAN_PKG::mylib;"
                      "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,SHARED_LIBRARY>:>;"
                      "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,MODULE_LIBRARY>:>;"
                      "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,EXECUTABLE>:>>;"
                      "$<$<CONFIG:MinSizeRel>:;CONAN_PKG::mylib;"
                      "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,SHARED_LIBRARY>:>;"
                      "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,MODULE_LIBRARY>:>;"
                      "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,EXECUTABLE>:>>;"
                      "$<$<CONFIG:Debug>:;CONAN_PKG::mylib;"
                      "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,SHARED_LIBRARY>:>;"
                      "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,MODULE_LIBRARY>:>;"
                      "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,EXECUTABLE>:>>",
                      client.out)
        self.assertIn("CONAN_LIB::myotherlib_lib2 libs: ;sys2;;CONAN_PKG::mylib", client.out)

    def test_user_appended_libs(self):
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

    def test_conan_get_policy(self):
        # https://github.com/conan-io/conan/issues/6974
        file_content = textwrap.dedent("""
            from conans import ConanFile, CMake

            class ConanFileToolsTest(ConanFile):
                name = "consumer"
                version = "1.0"
                generators = "cmake"
                settings = "os", "compiler", "arch", "build_type"
                exports_sources = "CMakeLists.txt"

                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
                """)

        cmakelists = textwrap.dedent("""
            cmake_minimum_required(VERSION 2.8)
            PROJECT(conanzlib LANGUAGES NONE)
            set(CONAN_DISABLE_CHECK_COMPILER TRUE)
            # test with any old build policy as we may
            # not have cmake version that supports 091
            cmake_policy(SET CMP0054 OLD)
            include(conanbuildinfo.cmake)
            conan_get_policy(CMP0054 policy_0054)
            message("POLICY CMP0054 IS ${policy_0054}")
            CONAN_BASIC_SETUP()
            """)
        client = TestClient()
        client.save({"conanfile.py": file_content,
                     "CMakeLists.txt": cmakelists})

        client.run('create .')
        self.assertIn("POLICY CMP0054 IS OLD", client.out)

    def test_do_not_mix_cflags_cxxflags(self):
        client = TestClient()

        def run_test(consumer_generator, consumer_cmakelists, with_components=True):

            def generate_files(upstream_cpp_info, consumer_generator, consumer_cmakelists):
                upstream_conanfile = GenConanfile().with_name("upstream").with_version("1.0")\
                    .with_package_info(cpp_info=upstream_cpp_info, env_info={})
                client.save({"conanfile.py": upstream_conanfile}, clean_first=True)
                client.run("create .")
                consumer_conanfile = textwrap.dedent("""
                    from conans import ConanFile, CMake

                    class Consumer(ConanFile):
                        name = "consumer"
                        version = "1.0"
                        settings = "os", "compiler", "arch", "build_type"
                        exports_sources = "CMakeLists.txt"
                        requires = "upstream/1.0"
                        generators = "{}"

                        def build(self):
                            cmake = CMake(self)
                            cmake.configure()
                    """)
                client.save({"conanfile.py": consumer_conanfile.format(consumer_generator),
                             "CMakeLists.txt": consumer_cmakelists})
                client.run("create .")

            if consumer_generator in ["cmake_find_package", "cmake_find_package_multi"]:
                if with_components:
                    cpp_info = {"components": {"comp": {"cflags": ["one", "two"],
                                                        "cxxflags": ["three", "four"]}}}
                else:
                    cpp_info = {"cflags": ["one", "two"], "cxxflags": ["three", "four"]}
                generate_files(cpp_info, consumer_generator, consumer_cmakelists)
                self.assertIn("compile options: three;four;one;two", client.out)
                self.assertIn("cflags: one;two", client.out)
                self.assertIn("cxxflags: three;four", client.out)
                if with_components:
                    self.assertIn("comp cflags: one;two", client.out)
                    self.assertIn("comp cxxflags: three;four", client.out)
                    if consumer_generator == "cmake_find_package":
                        self.assertIn("comp compile options: one;two;three;four", client.out)
                    else:
                        self.assertIn("$<$<CONFIG:Debug>:;>;"
                                      "$<$<CONFIG:Release>:;one;two;three;four>;"
                                      "$<$<CONFIG:RelWithDebInfo>:;>;"
                                      "$<$<CONFIG:MinSizeRel>:;>"
                                      , client.out)
            else:
                generate_files({"cflags": ["one", "two"], "cxxflags": ["three", "four"]},
                               consumer_generator, consumer_cmakelists)
                self.assertIn("global cflags: one two", client.out)
                self.assertIn("global cxxflags: three four", client.out)
                self.assertIn("upstream cflags: one two", client.out)
                self.assertIn("upstream cxxflags: three four", client.out)

        # Test cmake generator
        cmakelists = textwrap.dedent("""
            cmake_minimum_required(VERSION 2.8)
            set(CMAKE_CXX_COMPILER_WORKS 1)
            project(consumer)
            include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
            message("global cflags: ${CONAN_C_FLAGS}")
            message("global cxxflags: ${CONAN_CXX_FLAGS}")
            message("upstream cflags: ${CONAN_C_FLAGS_UPSTREAM}")
            message("upstream cxxflags: ${CONAN_CXX_FLAGS_UPSTREAM}")
            """)
        run_test("cmake", cmakelists)

        # Test cmake_multi generator
        cmakelists = textwrap.dedent("""
            cmake_minimum_required(VERSION 2.8)
            set(CMAKE_CXX_COMPILER_WORKS 1)
            project(consumer)
            include(${CMAKE_BINARY_DIR}/conanbuildinfo_multi.cmake)
            message("global cflags: ${CONAN_C_FLAGS_RELEASE}")
            message("global cxxflags: ${CONAN_CXX_FLAGS_RELEASE}")
            message("upstream cflags: ${CONAN_C_FLAGS_UPSTREAM_RELEASE}")
            message("upstream cxxflags: ${CONAN_CXX_FLAGS_UPSTREAM_RELEASE}")
            """)
        run_test("cmake_multi", cmakelists)

        # Test cmake_find_package generator
        cmakelists = textwrap.dedent("""
            cmake_minimum_required(VERSION 2.8)
            set(CMAKE_CXX_COMPILER_WORKS 1)
            project(consumer)
            find_package(upstream)
            message("compile options: ${upstream_COMPILE_OPTIONS_LIST}")
            message("cflags: ${upstream_COMPILE_OPTIONS_C}")
            message("cxxflags: ${upstream_COMPILE_OPTIONS_CXX}")
            message("comp cflags: ${upstream_comp_COMPILE_OPTIONS_C}")
            message("comp cxxflags: ${upstream_comp_COMPILE_OPTIONS_CXX}")
            get_target_property(tmp upstream::comp INTERFACE_COMPILE_OPTIONS)
            message("comp compile options: ${tmp}")
            """)
        run_test("cmake_find_package", cmakelists)

        # Test cmake_find_package generator without components
        run_test("cmake_find_package", cmakelists, with_components=False)

        # Test cmake_find_package_multi generator
        cmakelists = textwrap.dedent("""
            cmake_minimum_required(VERSION 2.8)
            set(CMAKE_CXX_COMPILER_WORKS 1)
            project(consumer)
            find_package(upstream)
            message("compile options: ${upstream_COMPILE_OPTIONS_RELEASE_LIST}")
            message("cflags: ${upstream_COMPILE_OPTIONS_C_RELEASE}")
            message("cxxflags: ${upstream_COMPILE_OPTIONS_CXX_RELEASE}")
            message("comp cflags: ${upstream_comp_COMPILE_OPTIONS_C_RELEASE}")
            message("comp cxxflags: ${upstream_comp_COMPILE_OPTIONS_CXX_RELEASE}")
            get_target_property(tmp upstream::comp INTERFACE_COMPILE_OPTIONS)
            message("comp compile options: ${tmp}")
            """)
        run_test("cmake_find_package_multi", cmakelists)

        # Test cmake_find_package_multi generator without components
        run_test("cmake_find_package_multi", cmakelists, with_components=False)

    def test_build_modules_alias_target(self, use_components=False):
        client = TestClient()
        conanfile = textwrap.dedent("""
            import os
            from conans import ConanFile, CMake

            class Conan(ConanFile):
                name = "hello"
                version = "1.0"
                settings = "os", "arch", "compiler", "build_type"
                exports_sources = ["target-alias.cmake"]

                def package(self):
                    self.copy("target-alias.cmake", dst="share/cmake")

                def package_info(self):
                    module = os.path.join("share", "cmake", "target-alias.cmake")
                    self.cpp_info.libs = ["hello"]
                    self.cpp_info.build_modules["cmake"].append(module)
            """)
        target_alias = textwrap.dedent("""
            add_library(otherhello INTERFACE IMPORTED)
            target_link_libraries(otherhello INTERFACE hello::hello)
            """)
        client.save({"conanfile.py": conanfile, "target-alias.cmake": target_alias})
        client.run("create .")

        consumer = textwrap.dedent("""
            from conans import ConanFile, CMake

            class Conan(ConanFile):
                name = "consumer"
                version = "1.0"
                settings = "os", "compiler", "build_type", "arch"
                exports_sources = ["CMakeLists.txt"]
                generators = "cmake"
                requires = "hello/1.0"

                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
            """)
        cmakelists = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.0)
            project(test)
            include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
            conan_basic_setup(TARGETS)
            get_target_property(tmp otherhello INTERFACE_LINK_LIBRARIES)
            message("otherhello link libraries: ${tmp}")
            """)
        client.save({"conanfile.py": consumer, "CMakeLists.txt": cmakelists})
        client.run("create .")
        assert "otherhello link libraries: hello::hello" in client.out
