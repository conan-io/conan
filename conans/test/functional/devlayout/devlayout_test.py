import os
import platform
import textwrap
import unittest

from nose.plugins.attrib import attr
from parameterized import parameterized

from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient, TurboTestClient
from conans.util.files import mkdir
from replace_version import replace_in_file


@attr("slow")
class DevLayoutTest(unittest.TestCase):
    conanfile = textwrap.dedent("""
        from conans import ConanFile, CMake, CMakeLayout

        class Pkg(ConanFile):
            settings = "os", "compiler", "arch", "build_type"
            options = {"shared": [True, False]}
            default_options = {"shared": False}
            generators = "cmake"
            exports_sources = "src/*", "CMakeLists.txt"
            generators = "cmake"
            layout = "cmake"
            
            def build(self):
                cmake = CMake(self) # Opt-in is defined having toolchain
                cmake.configure()
                cmake.build()

            def package(self):
                self.lyt.package()

            def package_info(self):
                self.lyt.package_info()
                self.cpp_info.libs = ["hello"]
            """)
    cmake = textwrap.dedent("""
        cmake_minimum_required(VERSION 2.8.12)
        set(CMAKE_CXX_COMPILER_WORKS 1)
        set(CMAKE_CXX_ABI_COMPILED 1)    
        project(HelloWorldLib CXX)
        
        include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
        conan_basic_setup()

        add_library(hello src/hello.cpp)
        add_executable(app src/app.cpp)
        target_link_libraries(app PRIVATE hello)
        """)
    hellopp = textwrap.dedent("""
        #include "hello.h"

        std::string hello(){
            #ifdef 	_M_IX86
                #ifdef NDEBUG
                return  "Hello World Release 32bits!";
                #else
                return  "Hello World Debug 32bits!";
                #endif
            #else
                #ifdef NDEBUG
                return  "Hello World Release!";
                #else
                return  "Hello World Debug!";
                #endif
            #endif
        }
        """)
    helloh = textwrap.dedent("""
        #pragma once
        #include <string>

        #ifdef WIN32
          #define HELLO_EXPORT __declspec(dllexport)
        #else
          #define HELLO_EXPORT
        #endif

        HELLO_EXPORT 
        std::string hello();
        """)
    app = textwrap.dedent(r"""
        #include <iostream>
        #include "hello.h"

        int main(){
            std::cout << "****\n" << hello() << "\n****\n\n";
        }
        """)
    test_cmake = textwrap.dedent("""
        cmake_minimum_required(VERSION 2.8.12)
        set(CMAKE_CXX_COMPILER_WORKS 1)
        set(CMAKE_CXX_ABI_COMPILED 1)

        project(Greet CXX)

        include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
        conan_basic_setup()

        add_executable(app app.cpp)
        MESSAGE(" CONAN LIBS=> ${CONAN_LIBS}")
        target_link_libraries(app ${CONAN_LIBS})
        """)
    test_conanfile = textwrap.dedent("""
        import os
        from conans import ConanFile, CMake, tools

        class Test(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            generators = "cmake"

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()
            
            def imports(self):
                self.copy(pattern="*.dll", dst="bin", src="bindir")

            def test(self):
                os.chdir("bin")
                self.run(".%sapp" % os.sep)
        """)

    def setUp(self):
        client = TestClient()
        client.save({"conanfile.py": self.conanfile,
                     "CMakeLists.txt": self.cmake,
                     "src/hello.cpp": self.hellopp,
                     "src/hello.h": self.helloh,
                     "src/app.cpp": self.app,
                     "test_package/app.cpp": self.app,
                     "test_package/CMakeLists.txt": self.test_cmake,
                     "test_package/conanfile.py": self.test_conanfile
                     })
        self.client = client

    def cache_create_test(self):
        # Cache creation
        client = TurboTestClient(cache_folder=self.client.cache_folder,
                                 current_folder=self.client.current_folder)
        ref = ConanFileReference.loads("pkg/0.1@user/testing")
        pref = client.create(ref, conanfile=None)  # Use the created conanfile
        self.assertIn("pkg/0.1@user/testing package(): Packaged 1 '.h' file: hello.h", client.out)
        self.assertIn("Hello World Release!", client.out)
        pl = client.cache.package_layout(ref)
        # There is a "build" subfolder also in the cache
        self.assertTrue(os.path.exists(os.path.join(pl.build(pref.copy_clear_revs()), "build")))

    def cache_custom_layout_test(self):
        # We can even change the src and the package layout and it works
        client = TurboTestClient()
        conanfile = textwrap.dedent("""
                from conans import ConanFile, CMake, Layout

                class Pkg(ConanFile):
                    settings = "os", "compiler", "arch", "build_type"
                    generators = "cmake"
                    exports_sources = "src/*"
                    
                    def layout(self):
                        self.lyt = Layout(self)
                        self.lyt.src = "src"
                        self.lyt.build = "my_custom_build"
                        self.lyt.pkg_libdir = "lib_custom"
                        self.lyt.pkg_bindir = "bin_custom"

                    def build(self):
                        cmake = CMake(self) # Opt-in is defined having toolchain
                        cmake.configure()
                        cmake.build()

                    def package(self):
                        self.lyt.package()

                    def package_info(self):
                        self.lyt.package_info()
                        self.cpp_info.libs = ["hello"]
                    """)
        client.save({"conanfile.py": conanfile,
                     "src/CMakeLists.txt": self.cmake.replace("src/", ""),  # NOW IS AT "src"
                     "src/hello.cpp": self.hellopp,
                     "src/hello.h": self.helloh,
                     "src/app.cpp": self.app,
                     "test_package/app.cpp": self.app,
                     "test_package/CMakeLists.txt": self.test_cmake,
                     "test_package/conanfile.py": self.test_conanfile
                     })
        ref = ConanFileReference.loads("pkg/0.1@user/testing")
        pref = client.create(ref, conanfile=None)  # Use the created conanfile
        self.assertIn("pkg/0.1@user/testing package(): Packaged 1 '.h' file: hello.h", client.out)
        self.assertIn("Hello World Release!", client.out)
        pl = client.cache.package_layout(ref)
        # There is a "my_custom_build" subfolder also in the cache
        self.assertTrue(os.path.exists(os.path.join(pl.build(pref.copy_clear_revs()),
                                                    "my_custom_build")))

        # There is a "lib_custom" subfolder in the package
        lib_folder = os.path.join(pl.package(pref.copy_clear_revs()), "lib_custom")
        self.assertTrue(os.path.exists(lib_folder))
        # The lib is there
        contents = os.listdir(lib_folder)
        self.assertIn("hello", contents[0])

    @unittest.skipIf(platform.system() != "Windows", "Needs windows")
    def cache_create_shared_test(self):
        # Cache creation
        client = self.client
        client.run("create . pkg/0.1@user/testing -o pkg:shared=True")

        self.assertIn("pkg/0.1@user/testing package(): Packaged 1 '.dll' file: hello.dll",
                      client.out)
        self.assertIn("pkg/0.1@user/testing package(): Packaged 1 '.h' file: hello.h", client.out)
        self.assertIn("imports(): Copied 1 '.dll' file: hello.dll", client.out)
        self.assertIn("Hello World Release!", client.out)

    @parameterized.expand([(True,), (False,)])
    @unittest.skipIf(platform.system() != "Windows", "Needs windows")
    def local_build_test(self, shared):
        client = self.client
        mkdir(os.path.join(client.current_folder, "build"))
        client.run("install .")
        shared = "-DBUILD_SHARED_LIBS=ON" if shared else ""
        with client.chdir("build"):
            client.run_command('cmake ../src -G "Visual Studio 15 Win64" %s' % shared)
            client.run_command("cmake --build . --config Release")
            client.run_command(r"Release\\app.exe")
            self.assertIn("Hello World Release!", client.out)
            client.run_command("cmake --build . --config Debug")
            client.run_command(r"Debug\\app.exe")
            self.assertIn("Hello World Debug!", client.out)

        client.run("editable add . pkg/0.1@user/testing")
        # Consumer of editable package
        client2 = TestClient(cache_folder=client.cache_folder)
        consumer = textwrap.dedent("""
            import os
            from conans import ConanFile, CMake, tools, CMakeLayout

            class Consumer(ConanFile):
                settings = "os", "compiler", "build_type", "arch"
                requires = "pkg/0.1@user/testing"
                generators = "cmake_find_package_multi"
                layout = "cmake"
                    
                def imports(self):
                    self.copy(pattern="*.dll", dst=self.lyt.build_bin_folder, src="bindir")
            """)

        test_cmake = textwrap.dedent("""
            cmake_minimum_required(VERSION 2.8.12)
            set(CMAKE_CXX_COMPILER_WORKS 1)
            set(CMAKE_CXX_ABI_COMPILED 1)
            project(Greet CXX)
            set(CMAKE_MODULE_PATH ${CMAKE_BINARY_DIR} ${CMAKE_MODULE_PATH})
            set(CMAKE_PREFIX_PATH ${CMAKE_BINARY_DIR} ${CMAKE_PREFIX_PATH})
            find_package(pkg)
            
            add_executable(app app.cpp)
            target_link_libraries(app pkg::pkg)
            """)
        client2.save({"app.cpp": self.app,
                      "CMakeLists.txt": test_cmake,
                      "conanfile.py": consumer})
        client2.run("install .")
        client2.run("install . -s build_type=Debug")
        with client2.chdir("build"):
            client2.run_command('cmake .. -G "Visual Studio 15 Win64"')
            client2.run_command("cmake --build . --config Release")
            # alternative 1: imports() copy DLLs. Does not work for continuous dev
            #                ok for cached dependencies, different Debug/Release output
            # alternative 2: virtualrunenv switch debug/release???
            # alternative 3: environment in cmake => path in MSBuild
            client2.run_command(r"Release\\app.exe")
            self.assertIn("Hello World Release!", client2.out)
            client2.run_command("cmake --build . --config Debug")
            client2.run_command(r"Debug\\app.exe")
            self.assertIn("Hello World Debug!", client2.out)

        # do changes
        client.save({"src/hello.cpp": self.hellopp.replace("World", "Moon")})
        with client.chdir("build"):
            client.run_command("cmake --build . --config Release")
            client.run_command(r"Release\\app.exe")
            self.assertIn("Hello Moon Release!", client.out)
            client.run_command("cmake --build . --config Debug")
            client.run_command(r"Debug\\app.exe")
            self.assertIn("Hello Moon Debug!", client.out)

        # It is necessary to "install" again, to fire the imports() and copy the DLLs
        client2.run("install .")
        client2.run("install . -s build_type=Debug")
        with client2.chdir("build"):
            client2.run_command("cmake --build . --config Release")
            client2.run_command(r"Release\\app.exe")
            self.assertIn("Hello Moon Release!", client2.out)
            client2.run_command("cmake --build . --config Debug")
            client2.run_command(r"Debug\\app.exe")
            self.assertIn("Hello Moon Debug!", client2.out)

    def test_clion_layout(self):
        """It is not necessary to have the IDE to follow the clion layout"""
        client = TurboTestClient()
        conanfile = textwrap.dedent("""
                from conans import ConanFile, CMake

                class Pkg(ConanFile):
                    settings = "os", "compiler", "arch", "build_type"
                    exports_sources = "src/*", "CMakeLists.txt"
                    generators = "cmake"
                    layout = "clion"

                    def build(self):
                        cmake = CMake(self)
                        cmake.configure()
                        cmake.build()

                    def package(self):
                        self.lyt.package()

                    def package_info(self):
                        self.lyt.package_info()
                        self.cpp_info.libs = ["hello"]
                    """)
        client.save({"conanfile.py": conanfile,
                     "CMakeLists.txt": self.cmake,
                     "src/hello.cpp": self.hellopp,
                     "src/hello.h": self.helloh,
                     "src/app.cpp": self.app,
                     "test_package/app.cpp": self.app,
                     "test_package/CMakeLists.txt": self.test_cmake,
                     "test_package/conanfile.py": self.test_conanfile
                     })
        ref = ConanFileReference.loads("pkg/0.1@user/testing")
        pref = client.create(ref, conanfile=None)  # Use the created conanfile
        self.assertIn("pkg/0.1@user/testing package(): Packaged 1 '.h' file: hello.h", client.out)
        self.assertIn("Hello World Release!", client.out)
        pl = client.cache.package_layout(ref)
        # There is a "cmake-build-release" sub-folder also in the cache
        self.assertTrue(os.path.exists(os.path.join(pl.build(pref.copy_clear_revs()),
                                                    "cmake-build-release")))
        # The library is generated in that subfolder
        lib_folder = os.path.join(pl.build(pref.copy_clear_revs()), "cmake-build-release", "lib")
        self.assertTrue("hello" in os.listdir(lib_folder)[0])

        # We can repeat the create now with debug
        pref = client.create(ref, conanfile=None, args="-s build_type=Debug")
        self.assertIn("pkg/0.1@user/testing package(): Packaged 1 '.h' file: hello.h", client.out)
        self.assertIn("Hello World Debug!", client.out)
        pl = client.cache.package_layout(ref)
        self.assertTrue(os.path.exists(os.path.join(pl.build(pref.copy_clear_revs()),
                                                    "cmake-build-debug")))

        # The library is generated in that sub-folder
        lib_folder = os.path.join(pl.build(pref.copy_clear_revs()), "cmake-build-debug", "lib")
        self.assertTrue("hello" in os.listdir(lib_folder)[0])

        # If we use the local methods, the layout is also the same as the cache
        client.run("install .")
        self.assertTrue(os.path.exists(os.path.join(client.current_folder, "cmake-build-release")))
        self.assertFalse(os.path.exists(os.path.join(client.current_folder, "cmake-build-debug")))

        client.run("install . -s build_type=Debug")
        self.assertTrue(os.path.exists(os.path.join(client.current_folder, "cmake-build-debug")))

        # We can build and package, everything will be as expected
        client.run("build . -if=cmake-build-release")
        client.run("package . -if=cmake-build-release")
        lib_package_folder = os.path.join(client.current_folder, "package", "lib")
        self.assertTrue("hello" in os.listdir(lib_package_folder)[0])  # The library is there

    def disable_output_dirs_test(self):
        """If we disable the output dirs, the layout have to change accordingly, if
        we use a wrong layout the libs/headers are not copied and not propagated
        correctly for the editable-consumers"""
        client = TurboTestClient()
        conanfile = textwrap.dedent("""
                from conans import ConanFile, CMake, Layout

                class Pkg(ConanFile):
                    settings = "os", "compiler", "arch", "build_type"
                    exports_sources = "src/*", "CMakeLists.txt"
                    generators = "cmake"
                
                    def layout(self):
                       self.lyt = Layout(self)
                       self.lyt.build_libdir = "lib"
                       self.lyt.build_includedirs = ["src"]

                    def build(self):
                        cmake = CMake(self)
                        cmake.configure()
                        cmake.build()

                    def package(self):
                        self.lyt.package()

                    def package_info(self):
                        self.lyt.package_info()
                        self.cpp_info.libs = ["hello"]
                    """)
        client.save({"conanfile.py": conanfile,
                     "CMakeLists.txt": self.cmake.replace("conan_basic_setup()",
                                                          "conan_basic_setup(NO_OUTPUT_DIRS)"),
                     "src/hello.cpp": self.hellopp,
                     "src/hello.h": self.helloh,
                     "src/app.cpp": self.app,
                     "test_package/app.cpp": self.app,
                     "test_package/CMakeLists.txt": self.test_cmake,
                     "test_package/conanfile.py": self.test_conanfile
                     })
        ref = ConanFileReference.loads("pkg/0.1@user/testing")
        client.create(ref, conanfile=None, assert_error=True)
        # No library packaged correctly
        self.assertNotIn("Packaged 1 '.lib'", client.out)
        self.assertNotIn("Packaged 1 '.a'", client.out)

        # If the package is editable it also fail to find the library, I'll use the test_package
        # as a regular consumer injecting the reference
        client.run("editable add . pkg/0.1@user/testing")
        client.run("install .")
        client.run("build . -if=build")
        tc = self.test_conanfile.replace('generators = "cmake"',
                                         'generators = "cmake"\n'
                                         '    requires = "pkg/0.1@user/testing"')
        client.save({"test_package/conanfile.py": tc})
        tmp_folder = client.current_folder
        client.current_folder = os.path.join(client.current_folder, "test_package")
        client.run("install .")
        self.assertIn("pkg/0.1@user/testing from user folder - Editable", client.out)
        client.run("build .", assert_error=True)
        # FIXME: Fis this assert for all OSS
        if platform.system() == "Linux":
            self.assertIn("/usr/bin/ld: cannot find -lhello", client.out)

        # If we fix the build_libdir in the layout of the editable using the root
        # (because there is no adjustements of output dirs) then it works
        replace_in_file(os.path.join(tmp_folder, "conanfile.py"), 'ly.build_libdir = "lib"',
                        'ly.build_libdir = ""')
        client.run("install .")
        self.assertIn("pkg/0.1@user/testing from user folder - Editable", client.out)
        client.run("build .")
        self.assertIn("Built target app", client.out)

# TODO: another class without really building to check all the output dirs are correct and following
#       the layout
    # TODO: A test doing source(), checking correct dirs
    # TODO: Alter install folder and see everything works, verify where the files are put
    # TODO: Editable packages includedirs

# TODO: Same local test for linux

    # TODO: In other place: Test mocked autotools and cmake with layout
    # TODO: Test to demonstrate multiconfig?
    # TODO: Test the export of the layout file is blocked
    # TODO: Test changing layout in the test_package folder
