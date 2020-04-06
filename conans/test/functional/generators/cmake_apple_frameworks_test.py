import platform
import textwrap
import unittest

from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient


@unittest.skipUnless(platform.system() == "Darwin", "Only for MacOS")
class CMakeAppleFrameworksTestCase(unittest.TestCase):
    lib_ref = ConanFileReference.loads("lib/version")
    lib_conanfile = textwrap.dedent("""
        from conans import ConanFile

        class Lib(ConanFile):
            def package_info(self):
                self.cpp_info.frameworks.extend(['Foundation', 'CoreServices', 'CoreFoundation'])
    """)

    app_conanfile = textwrap.dedent("""
        from conans import ConanFile, CMake

        class App(ConanFile):
            requires = "{}"
            generators = "{{generator}}"
            
            def build(self):
                cmake = CMake(self)
                cmake.configure()
    """.format(lib_ref))

    def setUp(self):
        self.t = TestClient()
        self.t.save({'conanfile.py': self.lib_conanfile})
        self.t.run("create . {}@".format(self.lib_ref))

    def _check_frameworks_found(self, output):
        self.assertIn("/System/Library/Frameworks/Foundation.framework;", output)
        self.assertIn("/System/Library/Frameworks/CoreServices.framework;", output)
        self.assertIn("/System/Library/Frameworks/CoreFoundation.framework", output)

    def test_apple_framework_cmake(self):
        app_cmakelists = textwrap.dedent("""
            project(Testing CXX)

            include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
            conan_basic_setup()
            
            message(">>> CONAN_FRAMEWORKS_FOUND_LIB: ${CONAN_FRAMEWORKS_FOUND_LIB}")
        """)

        self.t.save({'conanfile.py': self.app_conanfile.format(generator="cmake"),
                     'CMakeLists.txt': app_cmakelists})
        self.t.run("install .")
        self.t.run("build .")
        self._check_frameworks_found(str(self.t.out))

    def test_apple_framework_cmake_find_package(self):
        app_cmakelists = textwrap.dedent("""
            project(Testing CXX)

            find_package(lib)
            
            message(">>> CONAN_FRAMEWORKS_FOUND_LIB: ${lib_FRAMEWORKS_FOUND}")
        """)

        self.t.save({'conanfile.py': self.app_conanfile.format(generator="cmake_find_package"),
                     'CMakeLists.txt': app_cmakelists})
        self.t.run("install .")
        self.t.run("build .")
        self._check_frameworks_found(str(self.t.out))


@unittest.skipUnless(platform.system() == "Darwin", "Only for MacOS")
class CMakeAppleOwnFrameworksTestCase(unittest.TestCase):
    conanfile = textwrap.dedent("""
                from conans import ConanFile, CMake, tools

                class AppleframeworkConan(ConanFile):
                    settings = "os", "compiler", "build_type", "arch"
                    generators = "cmake"
                    exports_sources = "src/*"
                    name = "mylibrary"
                    version = "1.0"
                    def build(self):
                        cmake = CMake(self)
                        xcrun = tools.XCRun(self.settings)
                        cmake.definitions.update({
                            'CMAKE_OSX_SYSROOT' : xcrun.sdk_path,
                            'CMAKE_OSX_ARCHITECTURES' : tools.to_apple_arch(self.settings.arch),
                        })
                        cmake.configure(source_folder="src")
                        cmake.build()
                        cmake.install()
                        self.run("otool -L '%s/lib/hello.framework/hello'" % self.build_folder)
                        self.run("otool -L '%s/hello.framework/hello'" % self.package_folder)

                    def package_info(self):
                        self.cpp_info.frameworkdirs.append(self.package_folder)
                        self.cpp_info.frameworks.append("hello")
                """)
    cmake = textwrap.dedent("""
                cmake_minimum_required(VERSION 2.8)
                project(MyHello CXX)

                include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
                conan_basic_setup()

                # set @rpaths for libraries to link against
                SET(CMAKE_SKIP_RPATH FALSE)
                #SET(CMAKE_SKIP_BUILD_RPATH  FALSE)
                #SET(CMAKE_INSTALL_RPATH "@rpath/")
                #SET(CMAKE_INSTALL_RPATH_USE_LINK_PATH TRUE)

                add_library(hello SHARED hello.cpp hello.h)
                set_target_properties(hello PROPERTIES
                  FRAMEWORK TRUE
                  FRAMEWORK_VERSION A
                  MACOSX_FRAMEWORK_IDENTIFIER com.cmake.hello
                  MACOSX_FRAMEWORK_INFO_PLIST src/Info.plist
                  # "current version" in semantic format in Mach-O binary file
                  VERSION 1.6.0
                  # "compatibility version" in semantic format in Mach-O binary file
                  SOVERSION 1.6.0
                  PUBLIC_HEADER hello.h
                  INSTALL_NAME_DIR "@rpath"
                  MACOSX_RPATH TRUE
                )
                install(TARGETS hello DESTINATION ".")
            """)
    hello_h = textwrap.dedent("""
                #pragma once

                #ifdef WIN32
                  #define HELLO_EXPORT __declspec(dllexport)
                #else
                  #define HELLO_EXPORT __attribute__((visibility("default")))
                #endif

                #ifdef __cplusplus
                extern "C" {
                #endif
                class HELLO_EXPORT Hello
                {
                    public:
                        static void hello();
                };
                #ifdef __cplusplus
                }
                #endif
            """)
    hello_cpp = textwrap.dedent("""
                #include <iostream>
                #include "hello.h"

                void Hello::hello(){
                    #ifdef NDEBUG
                    std::cout << "Hello World Release!" <<std::endl;
                    #else
                    std::cout << "Hello World Debug!" <<std::endl;
                    #endif
                }
            """)
    infoplist = textwrap.dedent("""
                <?xml version="1.0" encoding="UTF-8"?>
                <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
                         "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
                <plist version="1.0">
                <dict>
                    <key>CFBundleDisplayName</key>
                    <string>hello</string>
                    <key>CFBundleExecutable</key>
                    <string>hello</string>
                    <key>CFBundleIdentifier</key>
                    <string>com.test.hello</string>
                    <key>CFBundleInfoDictionaryVersion</key>
                    <string>6.0</string>
                    <key>CFBundleName</key>
                    <string>hello</string>
                    <key>CFBundlePackageType</key>
                    <string>FMWK</string>
                    <key>CFBundleShortVersionString</key>
                    <string>1.6.0</string>
                    <key>CFBundleVersion</key>
                    <string>1.6.0</string>
                    <key>Flavor_ID</key>
                    <string>0</string>
                    <key>NSAppTransportSecurity</key>
                    <dict>
                        <key>NSAllowsArbitraryLoads</key>
                        <true/>
                    </dict>
                    <key>NSPrincipalClass</key>
                    <string></string>
                </dict>
                </plist>
            """)
    timer_cpp = textwrap.dedent("""
        #include <hello/hello.h>
        int main(){
            Hello::hello();
        }
        """)

    def test_apple_own_framework_cmake(self):
        client = TestClient()

        test_cmake = textwrap.dedent("""
            project(Testing CXX)
            include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
            conan_basic_setup()
            message(">>> CONAN_FRAMEWORKS_FOUND_MYLIBRARY: ${CONAN_FRAMEWORKS_FOUND_MYLIBRARY}")
            add_executable(timer timer.cpp)
            target_link_libraries(timer ${CONAN_LIBS})
        """)

        test_conanfile = textwrap.dedent("""
            from conans import ConanFile, CMake
            class TestPkg(ConanFile):
                generators = "cmake"
                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
                    cmake.build()
                def test(self):
                    self.run("bin/timer", run_environment=True)
            """)
        client.save({'conanfile.py': self.conanfile,
                     "src/CMakeLists.txt": self.cmake,
                     "src/hello.h": self.hello_h,
                     "src/hello.cpp": self.hello_cpp,
                     "src/Info.plist": self.infoplist,
                     "test_package/conanfile.py": test_conanfile,
                     'test_package/CMakeLists.txt': test_cmake,
                     "test_package/timer.cpp": self.timer_cpp})
        client.run("create .")
        self.assertIn("Hello World Release!", client.out)

    def test_apple_own_framework_cmake_find_package_multi(self):
        client = TestClient()

        test_cmake = textwrap.dedent("""
            project(Testing CXX)
            set(CMAKE_RUNTIME_OUTPUT_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}/bin")
            set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_DEBUG "${CMAKE_CURRENT_BINARY_DIR}/bin")
            set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_RELEASE "${CMAKE_CURRENT_BINARY_DIR}/bin")
            find_package(mylibrary REQUIRED)
            message(">>> CONAN_FRAMEWORKS_FOUND_MYLIBRARY: ${CONAN_FRAMEWORKS_FOUND_MYLIBRARY}")
            add_executable(timer timer.cpp)
            target_link_libraries(timer mylibrary::mylibrary)
        """)

        test_conanfile = textwrap.dedent("""
            from conans import ConanFile, CMake
            class TestPkg(ConanFile):
                generators = "cmake_find_package_multi"
                settings = "build_type",
                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
                    cmake.build()
                def test(self):
                    self.run("bin/timer", run_environment=True)
            """)
        client.save({'conanfile.py': self.conanfile,
                     "src/CMakeLists.txt": self.cmake,
                     "src/hello.h": self.hello_h,
                     "src/hello.cpp": self.hello_cpp,
                     "src/Info.plist": self.infoplist,
                     "test_package/conanfile.py": test_conanfile,
                     'test_package/CMakeLists.txt': test_cmake,
                     "test_package/timer.cpp": self.timer_cpp})
        client.run("create .")
        self.assertIn("Hello World Release!", client.out)
