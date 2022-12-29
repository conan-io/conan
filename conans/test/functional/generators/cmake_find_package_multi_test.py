import os
import platform
import textwrap
import unittest

import pytest

from conans.model.ref import ConanFileReference, PackageReference
from conans.test.assets.sources import gen_function_cpp, gen_function_h
from conans.test.utils.tools import TestClient, NO_SETTINGS_PACKAGE_ID, replace_in_file
from conans.util.files import load


@pytest.mark.tool_cmake
class TestCMakeFindPackageMultiGenerator:

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
                self.cpp_info.filenames["cmake_find_package_multi"] = "hello"
                self.cpp_info.components["comp"].libs = ["hello"]
                self.cpp_info.components["comp"].build_modules["cmake_find_package_multi"].append(module)
                """)
        else:
            info = textwrap.dedent("""\
                self.cpp_info.libs = ["hello"]
                self.cpp_info.build_modules["cmake_find_package_multi"].append(module)
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
                generators = "cmake_find_package_multi"
                requires = "hello/1.0"

                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
            """)
        cmakelists = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.0)
            project(test)
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
class CMakeFindPathMultiGeneratorTest(unittest.TestCase):

    def test_native_export_multi(self):
        """
        bye depends on hello. Both use find_package in their CMakeLists.txt
        The consumer depends on bye, using the cmake_find_package_multi generator
        """
        c = TestClient()
        project_folder_name = "project_targets"
        c.copy_assets("cmake_find_package_multi", ["bye", "hello", project_folder_name])

        # Create packages for hello and bye
        for p in ("hello", "bye"):
            for bt in ("Debug", "Release"):
                c.run("create {} user/channel -s build_type={}".format(p, bt))

        with c.chdir(project_folder_name):
            # Save conanfile and example
            conanfile = textwrap.dedent("""
                [requires]
                bye/1.0@user/channel

                [generators]
                cmake_find_package_multi
                """)
            example_cpp = gen_function_cpp(name="main", includes=["bye"], calls=["bye"])
            c.save({"conanfile.txt": conanfile, "example.cpp": example_cpp})

            with c.chdir("build"):
                for bt in ("Debug", "Release"):
                    c.run("install .. user/channel -s build_type={}".format(bt))

                # Test that we are using find_dependency with the NO_MODULE option
                # to skip finding first possible FindBye somewhere
                self.assertIn("find_dependency(hello REQUIRED NO_MODULE)",
                              load(os.path.join(c.current_folder, "bye-config.cmake")))

                if platform.system() == "Windows":
                    c.run_command('cmake .. -G "Visual Studio 15 Win64"')
                    c.run_command('cmake --build . --config Debug')
                    c.run_command('cmake --build . --config Release')

                    c.run_command('Debug\\example.exe')
                    self.assertIn("Hello World Debug!", c.out)
                    self.assertIn("bye World Debug!", c.out)

                    c.run_command('Release\\example.exe')
                    self.assertIn("Hello World Release!", c.out)
                    self.assertIn("bye World Release!", c.out)
                else:
                    for bt in ("Debug", "Release"):
                        c.run_command('cmake .. -DCMAKE_BUILD_TYPE={}'.format(bt))
                        c.run_command('cmake --build .')
                        c.run_command('./example')
                        self.assertIn("Hello World {}!".format(bt), c.out)
                        self.assertIn("bye World {}!".format(bt), c.out)
                        os.remove(os.path.join(c.current_folder, "example"))

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
            function(conan_message MESSAGE_OUTPUT)
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
        self.assertEqual(set(os.listdir(modules_path)),
                         {"FindFindModule.cmake", "my-module.cmake"})
        consumer = textwrap.dedent("""
            from conans import ConanFile, CMake

            class Conan(ConanFile):
                name = "consumer"
                version = "1.0"
                settings = "os", "compiler", "build_type", "arch"
                exports_sources = ["CMakeLists.txt"]
                generators = "cmake_find_package_multi"
                requires = "test/1.0"

                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
                    cmake.build()
            """)
        cmakelists = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.0)
            project(test)
            find_package(test)
            conan_message("Printing using a external module!")
            """)
        client.save({"conanfile.py": consumer, "CMakeLists.txt": cmakelists})
        client.run("create .")
        self.assertIn("Printing using a external module!", client.out)

    def test_cmake_find_package_system_libs(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile, tools

            class Test(ConanFile):
                name = "Test"
                version = "0.1"
                settings = "build_type"
                def package_info(self):
                    self.cpp_info.libs = ["lib1"]
                    if self.settings.build_type == "Debug":
                        self.cpp_info.system_libs.append("sys1d")
                    else:
                        self.cpp_info.system_libs.append("sys1")
            """)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("export .")

        conanfile = textwrap.dedent("""
            [requires]
            Test/0.1

            [generators]
            cmake_find_package_multi
            """)
        cmakelists_release = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.1)
            set(CMAKE_CXX_COMPILER_WORKS 1)
            set(CMAKE_CXX_ABI_COMPILED 1)
            project(consumer CXX)
            set(CMAKE_PREFIX_PATH ${CMAKE_BINARY_DIR})
            set(CMAKE_MODULE_PATH ${CMAKE_BINARY_DIR})
            find_package(Test)
            message("System libs: ${Test_SYSTEM_LIBS_RELEASE}")
            message("Libraries to Link: ${Test_LIBS_RELEASE}")
            get_target_property(tmp Test::Test INTERFACE_LINK_LIBRARIES)
            message("Target libs: ${tmp}")
            """)
        cmakelists_debug = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.1)
            set(CMAKE_CXX_COMPILER_WORKS 1)
            set(CMAKE_CXX_ABI_COMPILED 1)
            project(consumer CXX)
            set(CMAKE_PREFIX_PATH ${CMAKE_BINARY_DIR})
            set(CMAKE_MODULE_PATH ${CMAKE_BINARY_DIR})
            find_package(Test)
            message("System libs: ${Test_SYSTEM_LIBS_DEBUG}")
            message("Libraries to Link: ${Test_LIBS_DEBUG}")
            get_target_property(tmp Test::Test INTERFACE_LINK_LIBRARIES)
            message("Target libs: ${tmp}")
            """)
        for build_type in ["Release", "Debug"]:
            cmakelists = cmakelists_release if build_type == "Release" else cmakelists_debug
            client.save({"conanfile.txt": conanfile, "CMakeLists.txt": cmakelists}, clean_first=True)
            client.run("install conanfile.txt --build missing -s build_type=%s" % build_type)
            client.run_command('cmake . -DCMAKE_BUILD_TYPE={0}'.format(build_type))

            library_name = "sys1d" if build_type == "Debug" else "sys1"
            self.assertIn("System libs: %s" % library_name, client.out)
            self.assertIn("Libraries to Link: lib1", client.out)
            self.assertNotIn("-- Library %s not found in package, might be system one" %
                             library_name, client.out)
            if build_type == "Release":
                target_libs = ("$<$<CONFIG:Debug>:;>;"
                               "$<$<CONFIG:Release>:lib1;sys1;"
                               "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,SHARED_LIBRARY>:>;"
                               "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,MODULE_LIBRARY>:>;"
                               "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,EXECUTABLE>:>>;"
                               "$<$<CONFIG:RelWithDebInfo>:;>;$<$<CONFIG:MinSizeRel>:;>")
            else:
                target_libs = ("$<$<CONFIG:Debug>:lib1;sys1d;"
                               "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,SHARED_LIBRARY>:>;"
                               "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,MODULE_LIBRARY>:>;"
                               "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,EXECUTABLE>:>>;"
                               "$<$<CONFIG:Release>:;>;"
                               "$<$<CONFIG:RelWithDebInfo>:;>;$<$<CONFIG:MinSizeRel>:;>")
            self.assertIn("Target libs: %s" % target_libs, client.out)

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
            cmake_minimum_required(VERSION 3.1)
            project(consumer)
            find_package(MYHELLO2)

            get_target_property(tmp MYHELLO2::MYHELLO2 INTERFACE_LINK_LIBRARIES)
            message("Target libs (hello2): ${tmp}")
            get_target_property(tmp MYHELLO::MYHELLO INTERFACE_LINK_LIBRARIES)
            message("Target libs (hello): ${tmp}")
            """)
        conanfile = textwrap.dedent("""
            from conans import ConanFile, CMake

            class Conan(ConanFile):
                settings = "build_type"
                requires = "hello2/1.0"
                generators = "cmake_find_package_multi"

                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
            """)
        client.save({"conanfile.py": conanfile, "CMakeLists.txt": cmakelists})
        client.run("install .")
        client.run("build .")
        assert ("Target libs (hello2): "
                "$<$<CONFIG:Debug>:;>;"
                "$<$<CONFIG:Release>:CONAN_LIB::MYHELLO2_hello2_RELEASE;MYHELLO::MYHELLO;"
                "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,SHARED_LIBRARY>:>;"
                "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,MODULE_LIBRARY>:>;"
                "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,EXECUTABLE>:>>;"
                "$<$<CONFIG:RelWithDebInfo>:;>;$<$<CONFIG:MinSizeRel>:;>") in client.out

        assert ("Target libs (hello): "
                "$<$<CONFIG:Debug>:;>;"
                "$<$<CONFIG:Release>:CONAN_LIB::MYHELLO_hello_RELEASE;"
                "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,SHARED_LIBRARY>:>;"
                "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,MODULE_LIBRARY>:>;"
                "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,EXECUTABLE>:>>;"
                "$<$<CONFIG:RelWithDebInfo>:;>;$<$<CONFIG:MinSizeRel>:;>") in client.out

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

        t.run("install requirement/version@ -g cmake_find_package_multi -s build_type=Release")
        t.run("install requirement/version@ -g cmake_find_package_multi -s build_type=Debug")
        content_release = t.load("requirementTarget-release.cmake")
        content_debug = t.load("requirementTarget-debug.cmake")

        self.assertIn('set(requirement_COMPILE_OPTIONS_RELEASE_LIST "-req_both;-req_release" "")',
                      content_release)
        self.assertIn('set(requirement_COMPILE_OPTIONS_DEBUG_LIST "-req_both;-req_debug" "")',
                      content_debug)

        self.assertIn('set(requirement_LIBRARY_LIST_RELEASE lib_both lib_release)', content_release)
        self.assertIn('set(requirement_LIBRARY_LIST_DEBUG lib_both lib_debug)', content_debug)

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
                generators = "cmake_find_package_multi"
                exports_sources = "CMakeLists.txt"
                settings = "os", "arch", "compiler", "build_type"

                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
        """)

        cmakelists = textwrap.dedent("""
            project(consumer)
            cmake_minimum_required(VERSION 3.1)
            find_package(requirement)
            get_target_property(tmp requirement::component INTERFACE_LINK_LIBRARIES)
            message("component libs: ${tmp}")
        """)

        t.save({"conanfile.py": conanfile, "CMakeLists.txt": cmakelists})
        t.run("create . --build missing -s build_type=Release")

        assert ("component libs: $<$<CONFIG:Debug>:;>;"
                "$<$<CONFIG:Release>:system_lib_component;"
                "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,SHARED_LIBRARY>:>;"
                "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,MODULE_LIBRARY>:>;"
                "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,EXECUTABLE>:>>;"
                "$<$<CONFIG:RelWithDebInfo>:;>;$<$<CONFIG:MinSizeRel>:;>") in t.out


@pytest.mark.tool_cmake
class TestNoNamespaceTarget:
    """ This test case uses build-modules feature to create a target without a namespace. This
        target uses targets create by Conan (build_modules are included after Conan targets)
    """

    conanfile = textwrap.dedent("""
        import os
        from conans import ConanFile, CMake

        class Recipe(ConanFile):
            settings = "os", "compiler", "arch", "build_type"
            exports_sources = ["src/*", "build-module.cmake"]
            generators = "cmake"

            def build(self):
                cmake = CMake(self)
                cmake.configure(source_folder="src")
                cmake.build()

            def package(self):
                self.copy("*.h", dst="include", src="src")
                self.copy("*.lib", dst="lib", keep_path=False)
                self.copy("*.dll", dst="bin", keep_path=False)
                self.copy("*.dylib*", dst="lib", keep_path=False)
                self.copy("*.so", dst="lib", keep_path=False)
                self.copy("*.a", dst="lib", keep_path=False)
                self.copy("build-module.cmake", dst="share/cmake")

            def package_info(self):
                self.cpp_info.libs = ["library"]
                module = os.path.join("share", "cmake", "build-module.cmake")
                self.cpp_info.build_modules['cmake_find_package'] = [module, ]
                self.cpp_info.build_modules['cmake_find_package_multi'] = [module, ]
    """)

    build_module = textwrap.dedent("""
        message(">> Build-module is included")

        if(NOT TARGET nonamespace)
            add_library(nonamespace INTERFACE IMPORTED)
            target_link_libraries(nonamespace INTERFACE library::library)
        endif()
    """)

    consumer = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.0)
        set(CMAKE_CXX_COMPILER_WORKS 1)
        set(CMAKE_CXX_ABI_COMPILED 1)
        project(consumer)

        find_package(library)

        get_target_property(LIBS1 library::library INTERFACE_LINK_LIBRARIES)
        message(">> library::library libs: ${LIBS1}")

        get_target_property(LIBS2 nonamespace INTERFACE_LINK_LIBRARIES)
        message(">> nonamespace libs: ${LIBS2}")

        add_executable(consumer main.cpp)
        target_link_libraries(consumer nonamespace)
    """)

    main = textwrap.dedent("""
        #include "library.h"

        int main() {
            library();
        }
    """)

    @classmethod
    def setup_class(cls):
        cls.t = t = TestClient()
        # Create a library providing a build-module
        t.run('new library/version -s')
        t.save({'conanfile.py': cls.conanfile,
                'build-module.cmake': cls.build_module})
        t.run('create conanfile.py library/version@ -s build_type=Debug')
        t.run('create conanfile.py library/version@ -s build_type=Release')
        # Prepare project to consume the targets
        t.save({'CMakeLists.txt': cls.consumer, 'main.cpp': cls.main}, clean_first=True)

    def test_non_multi_generator(self):
        t = self.t
        with t.chdir('not_multi'):
            t.run('install library/version@ -g cmake_find_package -s build_type=Release')
            generator = '-G "Visual Studio 15 Win64"' if platform.system() == "Windows" else ''
            t.run_command(
                'cmake .. {} -DCMAKE_MODULE_PATH:PATH="{}"'.format(generator, t.current_folder))
            assert str(t.out).count('>> Build-module is included') == 1
            assert '>> nonamespace libs: library::library' in t.out
            t.run_command('cmake --build .')  # Compiles and links.

    @pytest.mark.skipif(platform.system() != "Windows", reason="Only windows")
    @pytest.mark.tool_visual_studio
    def test_multi_generator_windows(self):
        t = self.t
        with t.chdir('multi_windows'):
            t.run('install library/version@ -g cmake_find_package_multi -s build_type=Release')
            t.run('install library/version@ -g cmake_find_package_multi -s build_type=Debug')
            generator = '-G "Visual Studio 15 Win64"'
            t.run_command(
                'cmake .. {} -DCMAKE_PREFIX_PATH:PATH="{}"'.format(generator, t.current_folder))
            assert str(t.out).count('>> Build-module is included') == 2  # FIXME: Known bug
            assert '>> nonamespace libs: library::library' in t.out
            t.run_command('cmake --build . --config Release')  # Compiles and links.

    @pytest.mark.skipif(platform.system() != "Darwin", reason="Requires Macos")
    @pytest.mark.tool_xcodebuild
    @pytest.mark.tool_cmake(version="3.19")
    def test_multi_generator_macos(self):
        t = self.t
        with t.chdir('multi_macos'):
            t.run('install library/version@ -g cmake_find_package_multi -s build_type=Release')
            t.run('install library/version@ -g cmake_find_package_multi -s build_type=Debug')
            t.run_command('cmake .. -G Xcode -DCMAKE_PREFIX_PATH:PATH="{}"'.format(t.current_folder))
            assert str(t.out).count('>> Build-module is included') == 2  # FIXME: Known bug
            assert '>> nonamespace libs: library::library' in t.out
            t.run_command('cmake --build . --config Release')  # Compiles and links.


@pytest.mark.skipif(platform.system() != "Linux", reason="Only Linux")
@pytest.mark.tool_cmake
def test_no_soname_flag():
    """ This test case is testing this graph structure:
            *   'LibNoSoname' -> 'OtherLib' -> 'Executable'
        Where:
            *   LibNoSoname: is a package built as shared and without the SONAME flag.
            *   OtherLib: is a package which requires LibNoSoname.
            *   Executable: is the final consumer building an application and depending on OtherLib.
    """
    client = TestClient()
    conanfile = textwrap.dedent("""
    from conans import ConanFile, CMake, tools

    class {name}Conan(ConanFile):
        name = "{name}"
        version = "1.0"

        # Binary configuration
        settings = "os", "compiler", "build_type", "arch"
        options = {{"shared": [True, False], "fPIC": [True, False]}}
        default_options = {{"shared": True, "fPIC": True}}

        # Sources are located in the same place as this recipe, copy them to the recipe
        exports_sources = "CMakeLists.txt", "src/*"
        generators = "cmake_find_package_multi"
        {requires}

        def config_options(self):
            if self.settings.os == "Windows":
                del self.options.fPIC

        def build(self):
            cmake = CMake(self)
            cmake.configure()
            cmake.build()

        def package(self):
            self.copy("*.h", dst="include", src="src")
            self.copy("*.lib", dst="lib", keep_path=False)
            self.copy("*.dll", dst="bin", keep_path=False)
            self.copy("*.so", dst="lib", keep_path=False)
            self.copy("*.dylib", dst="lib", keep_path=False)
            self.copy("*.a", dst="lib", keep_path=False)

        def package_info(self):
            self.cpp_info.libs = ["{name}"]
            self.cpp_info.names["cmake_find_package_multi"] = "{name}"
    """)
    cmakelists_nosoname = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(nosoname CXX)

        add_library(nosoname SHARED src/nosoname.cpp)

        # Adding NO_SONAME flag to main library
        set_target_properties(nosoname PROPERTIES PUBLIC_HEADER "src/nosoname.h" NO_SONAME 1)
        install(TARGETS nosoname DESTINATION "."
                PUBLIC_HEADER DESTINATION include
                RUNTIME DESTINATION bin
                ARCHIVE DESTINATION lib
                LIBRARY DESTINATION lib
                )
    """)
    cpp = gen_function_cpp(name="nosoname")
    h = gen_function_h(name="nosoname")
    client.save({"CMakeLists.txt": cmakelists_nosoname,
                 "src/nosoname.cpp": cpp,
                 "src/nosoname.h": h,
                 "conanfile.py": conanfile.format(name="nosoname", requires="")})
    # Now, let's create both libraries
    client.run("create .")
    cmakelists_libB = textwrap.dedent("""
    cmake_minimum_required(VERSION 3.15)
    project(libB CXX)

    find_package(nosoname CONFIG REQUIRED)

    add_library(libB SHARED src/libB.cpp)
    target_link_libraries(libB nosoname::nosoname)

    set_target_properties(libB PROPERTIES PUBLIC_HEADER "src/libB.h")
    install(TARGETS libB DESTINATION "."
            PUBLIC_HEADER DESTINATION include
            RUNTIME DESTINATION bin
            ARCHIVE DESTINATION lib
            LIBRARY DESTINATION lib
            )
    """)
    cpp = gen_function_cpp(name="libB", includes=["nosoname"], calls=["nosoname"])
    h = gen_function_h(name="libB")
    client.save({"CMakeLists.txt": cmakelists_libB,
                 "src/libB.cpp": cpp,
                 "src/libB.h": h,
                 "conanfile.py": conanfile.format(name="libB", requires='requires = "nosoname/1.0"')},
                clean_first=True)
    # Now, let's create both libraries
    client.run("create .")
    # Now, let's create the application consuming libB
    cmakelists = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(PackageTest CXX)

        include(${{CMAKE_BINARY_DIR}}/conanbuildinfo.cmake)
        conan_basic_setup()

        set(CMAKE_MODULE_PATH ${{CMAKE_BINARY_DIR}})
        set(CMAKE_PREFIX_PATH ${{CMAKE_BINARY_DIR}})

        find_package(libB CONFIG REQUIRED)

        add_executable(example src/example.cpp)
        target_link_libraries(example libB)
    """)
    conanfile = textwrap.dedent("""
        [requires]
        libB/1.0

        [generators]
        cmake
        cmake_find_package_multi
    """)
    cpp = gen_function_cpp(name="main", includes=["libB"], calls=["libB"])
    client.save({"CMakeLists.txt": cmakelists.format(current_folder=client.current_folder),
                 "src/example.cpp": cpp,
                 "conanfile.txt": conanfile},
                clean_first=True)
    client.run('install . ')
    client.run_command('cmake -G "Unix Makefiles" . && cmake --build . && ./bin/example')
