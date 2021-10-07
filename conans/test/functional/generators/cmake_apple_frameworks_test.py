import os
import platform
import textwrap
import unittest

import pytest

from parameterized import parameterized
from conans.client.tools.env import environment_append
from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only for MacOS")
@pytest.mark.tool_cmake
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
            settings = "build_type",  # cmake_multi doesn't work without build_type

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

    def test_apple_framework_cmake_multi(self):
        app_cmakelists = textwrap.dedent("""
            project(Testing CXX)

            include(${CMAKE_BINARY_DIR}/conanbuildinfo_multi.cmake)
            conan_basic_setup()

            message(">>> CONAN_FRAMEWORKS_FOUND_LIB_DEBUG: ${CONAN_FRAMEWORKS_FOUND_LIB_DEBUG}")
            message(">>> CONAN_FRAMEWORKS_FOUND_LIB_RELEASE: ${CONAN_FRAMEWORKS_FOUND_LIB_RELEASE}")
        """)

        self.t.save({'conanfile.py': self.app_conanfile.format(generator="cmake_multi"),
                     'CMakeLists.txt': app_cmakelists})
        self.t.run("install . -s build_type=Release")
        self.t.run("install . -s build_type=Debug")
        self.t.run("build .")
        self._check_frameworks_found(str(self.t.out))

    @pytest.mark.tool_cmake(version="3.19")
    def test_apple_framework_cmake_multi_xcode(self):
        app_cmakelists = textwrap.dedent("""
            project(Testing CXX)

            include(${CMAKE_BINARY_DIR}/conanbuildinfo_multi.cmake)
            conan_basic_setup()

            message(">>> CONAN_FRAMEWORKS_FOUND_LIB_DEBUG: ${CONAN_FRAMEWORKS_FOUND_LIB_DEBUG}")
            message(">>> CONAN_FRAMEWORKS_FOUND_LIB_RELEASE: ${CONAN_FRAMEWORKS_FOUND_LIB_RELEASE}")
        """)

        self.t.save({'conanfile.py': self.app_conanfile.format(generator="cmake_multi"),
                     'CMakeLists.txt': app_cmakelists})
        with environment_append({"CONAN_CMAKE_GENERATOR": "Xcode"}):
            self.t.run("install . -s build_type=Release")
            self.t.run("install . -s build_type=Debug")
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


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only for MacOS")
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

    @parameterized.expand([('',),
                           ('-s os=iOS -s os.version=10.0 -s arch=armv8',),
                           ("-s os=tvOS -s os.version=11.0 -s arch=armv8",)])
    def test_apple_own_framework_cmake(self, settings):
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
            from conans import ConanFile, CMake, tools
            class TestPkg(ConanFile):
                generators = "cmake"
                settings = "os", "arch", "compiler", "build_type"
                def build(self):
                    cmake = CMake(self)
                    cmake_system_name = {"Macos" : "Darwin",
                                         "iOS" : "iOS",
                                         "tvOS" : "tvOS"}[str(self.settings.os)]
                    archs = {
                        "Macos": "x86_64",
                        "iOS": "arm64;x86_64",
                        "tvOS": "arm64;x86_64",
                        }[str(self.settings.os)]
                    xcrun = tools.XCRun(self.settings)
                    cmake.definitions.update({
                        'CMAKE_OSX_SYSROOT': xcrun.sdk_path,
                        'CMAKE_SYSTEM_NAME': cmake_system_name,
                    })
                    cmake.configure()
                    cmake.build()
                def test(self):
                    if not tools.cross_building(self):
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
        client.run("create . %s" % settings)
        if not len(settings):
            self.assertIn("Hello World Release!", client.out)

    @pytest.mark.tool_cmake(version="3.19")
    def test_apple_own_framework_cmake_multi(self):
        client = TestClient()

        test_cmake = textwrap.dedent("""
            project(Testing CXX)
            message(STATUS "CMAKE_BINARY_DIR ${CMAKE_BINARY_DIR}")
            include(${CMAKE_BINARY_DIR}/../../conanbuildinfo_multi.cmake)
            conan_basic_setup()
            message(">>> CONAN_FRAMEWORKS_FOUND_MYLIBRARY_DEBUG: ${CONAN_FRAMEWORKS_FOUND_MYLIBRARY_DEBUG}")
            message(">>> CONAN_FRAMEWORKS_FOUND_MYLIBRARY_RELEASE: ${CONAN_FRAMEWORKS_FOUND_MYLIBRARY_RELEASE}")
            add_executable(timer timer.cpp)
            target_link_libraries(timer debug ${CONAN_LIBS_DEBUG} optimized ${CONAN_LIBS_RELEASE})
        """)

        test_conanfile = textwrap.dedent("""
            from conans import ConanFile, CMake
            class TestPkg(ConanFile):
                generators = "cmake_multi"
                name = "app"
                version = "1.0"
                requires = "mylibrary/1.0"
                exports_sources = "CMakeLists.txt", "timer.cpp"
                settings = "build_type",  # cmake_multi doesn't work without build_type
                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
                    cmake.build()
                def test(self):
                    self.run("%s/timer" % self.settings.build_type, run_environment=True)
            """)
        client.save({'conanfile.py': self.conanfile,
                     "src/CMakeLists.txt": self.cmake,
                     "src/hello.h": self.hello_h,
                     "src/hello.cpp": self.hello_cpp,
                     "src/Info.plist": self.infoplist})
        client.run("export . mylibrary/1.0@")
        client.run("create . mylibrary/1.0@ -s build_type=Debug")
        client.run("create . mylibrary/1.0@ -s build_type=Release")

        client.save({"conanfile.py": test_conanfile,
                     'CMakeLists.txt': test_cmake,
                     "timer.cpp": self.timer_cpp})
        with environment_append({"CONAN_CMAKE_GENERATOR": "Xcode"}):
            client.run("install . -s build_type=Debug")
            client.run("install . -s build_type=Release")
            client.run("test . mylibrary/1.0@")
            self.assertIn("Hello World Release!", client.out)
            client.run("test . mylibrary/1.0@ -s build_type=Debug")
            self.assertIn("Hello World Debug!", client.out)

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

    @parameterized.expand([('cmake', False),
                           ('cmake_find_package', False), ('cmake_find_package', True), ])
    def test_frameworks_exelinkflags(self, generator, use_components):
        # FIXME: Conan 2.0. 'cpp_info' object has a 'frameworks' key
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class Recipe(ConanFile):
                settings = "os", "arch", "compiler", "build_type"
                options = {'use_components': [True, False]}
                default_options = {'use_components': False}

                def package_info(self):
                    if not self.options.use_components:
                        self.cpp_info.exelinkflags.extend(['-framework Foundation'])
                        #self.cpp_info.frameworks.extend(['Foundation'])
                    else:
                        self.cpp_info.components["cmp"].exelinkflags.extend(['-framework Foundation'])
                        #self.cpp_info.components["cmp"].frameworks.extend(['Foundation'])
        """)
        tp_cmakelists = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.0)
            project(test_package)

            include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
            conan_basic_setup(TARGETS)

            if(USE_FIND_PACKAGE)
                message(">> USE_FIND_PACKAGE")
                find_package(name)
                add_executable(${PROJECT_NAME} test_package.cpp)
                if (USE_COMPONENTS)
                    message(">> USE_COMPONENTS")
                    target_link_libraries(${PROJECT_NAME} name::cmp)
                else()
                    message(">> not USE_COMPONENTS")
                    target_link_libraries(${PROJECT_NAME} name::name)
                endif()
            else()
                message(">> not USE_FIND_PACKAGE")
                add_executable(${PROJECT_NAME} test_package.cpp)
                target_link_libraries(${PROJECT_NAME} CONAN_PKG::name)
            endif()
        """)
        tp_conanfile = textwrap.dedent("""
            from conans import ConanFile, CMake

            class TestPackage(ConanFile):
                settings = "os", "arch", "compiler", "build_type"
                generators = "cmake", "cmake_find_package"
                options = {'use_find_package': [True, False]}
                requires = "name/version"

                def build(self):
                    cmake = CMake(self)
                    cmake.definitions["USE_FIND_PACKAGE"] = self.options.use_find_package
                    cmake.definitions["USE_COMPONENTS"] = self.options["name"].use_components
                    cmake.configure()
                    cmake.build()

                def test(self):
                    pass
        """)
        tp_main = textwrap.dedent("""
            int main() {}
        """)

        t = TestClient()
        t.save({'conanfile.py': conanfile,
                'test_package/conanfile.py': tp_conanfile,
                'test_package/CMakeLists.txt': tp_cmakelists,
                'test_package/test_package.cpp': tp_main})
        t.run("export conanfile.py name/version@")

        with t.chdir('test_package/build'):
            if generator == 'cmake':
                assert not use_components
                t.run("install .. --build=missing"
                      " -o name:use_components=False -o use_find_package=False")
                t.run("build ..")
                self.assertIn(">> not USE_FIND_PACKAGE", t.out)
            else:
                assert generator == 'cmake_find_package'
                t.run("install .. --build=missing"
                      " -o name:use_components={} -o use_find_package=True".format(use_components))
                t.run("build ..")
                self.assertIn(">> USE_FIND_PACKAGE", t.out)
                self.assertIn(">> {}USE_COMPONENTS".format("" if use_components else "not "), t.out)

            # Check we are using the framework
            link_txt = t.load(os.path.join('CMakeFiles', 'test_package.dir', 'link.txt'))
            self.assertIn("-framework Foundation", link_txt)

    def test_component(self):
        conanfile_py = textwrap.dedent("""
from conans import ConanFile, CMake, tools


class HelloConan(ConanFile):
    name = "hello"
    description = "example"
    topics = ("conan",)
    url = "https://github.com/conan-io/conan-center-index"
    homepage = "https://www.example.com"
    license = "MIT"
    exports_sources = ["hello.cpp", "hello.h", "CMakeLists.txt"]
    generators = "cmake"
    settings = "os", "arch", "compiler", "build_type"
    _source_subfolder = "source_subfolder"
    _build_subfolder = "build_subfolder"

    _cmake = None

    def source(self):
        pass

    def _configure_cmake(self):
        if self._cmake:
            return self._cmake
        self._cmake = CMake(self)
        self._cmake.configure(build_folder=self._build_subfolder)
        return self._cmake

    def build(self):
        cmake = self._configure_cmake()
        cmake.build()

    def package(self):
        cmake = self._configure_cmake()
        cmake.install()

    def package_info(self):
        self.cpp_info.names["cmake_find_package"] = "HELLO"
        self.cpp_info.names["cmake_find_package_multi"] = "HELLO"
        self.cpp_info.components["libhello"].names["cmake_find_package"] = "libhello"
        self.cpp_info.components["libhello"].names["cmake_find_package_multi"] = "libhello"

        self.cpp_info.components["libhello"].libs = ["hello"]
        self.cpp_info.components["libhello"].frameworks.extend(["CoreFoundation"])
        """)
        hello_cpp = textwrap.dedent("""
#include <CoreFoundation/CoreFoundation.h>

void hello_api()
{
    CFTypeRef keys[] = {CFSTR("key")};
    CFTypeRef values[] = {CFSTR("value")};
    CFDictionaryRef dict = CFDictionaryCreate(kCFAllocatorDefault, keys, values, sizeof(keys) / sizeof(keys[0]), &kCFTypeDictionaryKeyCallBacks, &kCFTypeDictionaryValueCallBacks);
    if (dict)
        CFRelease(dict);
}
        """)
        hello_h = textwrap.dedent("""
void hello_api();
        """)
        cmakelists_txt = textwrap.dedent("""
cmake_minimum_required(VERSION 2.8)

project(hello)

include(GNUInstallDirs)

include(conanbuildinfo.cmake)
conan_basic_setup()

file(GLOB SOURCES *.cpp)
file(GLOB HEADERS *.h)

add_library(${PROJECT_NAME} ${SOURCES} ${HEADERS})

set_target_properties(${PROJECT_NAME} PROPERTIES PUBLIC_HEADER ${HEADERS})
install(TARGETS ${PROJECT_NAME}
    RUNTIME DESTINATION bin
    LIBRARY DESTINATION lib
    ARCHIVE DESTINATION lib
    PUBLIC_HEADER DESTINATION include)
        """)
        tp_conanfile_py = textwrap.dedent("""
import os
from conans import ConanFile, CMake, tools

class TestPackageConan(ConanFile):
    settings = "os", "compiler", "build_type", "arch"
    generators = "cmake", "cmake_find_package_multi"

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()

    def test(self):
        if not tools.cross_building(self.settings):
            bin_path = os.path.join("bin", "test_package")
            self.run(bin_path, run_environment=True)
        """)
        tp_test_package_cpp = textwrap.dedent("""
#include "hello.h"

int main()
{
    hello_api();
}
        """)
        tp_cmakelists_txt = textwrap.dedent("""
cmake_minimum_required(VERSION 2.8)
project(test_package)

include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
conan_basic_setup()

find_package(HELLO REQUIRED CONFIG)

add_executable(${PROJECT_NAME} test_package.cpp)
target_link_libraries(${PROJECT_NAME} HELLO::libhello)
        """)
        t = TestClient()
        t.save({'conanfile.py': conanfile_py,
                'hello.cpp': hello_cpp,
                'hello.h': hello_h,
                'CMakeLists.txt': cmakelists_txt,
                'test_package/conanfile.py': tp_conanfile_py,
                'test_package/CMakeLists.txt': tp_cmakelists_txt,
                'test_package/test_package.cpp': tp_test_package_cpp})
        t.run("create . hello/1.0@")
