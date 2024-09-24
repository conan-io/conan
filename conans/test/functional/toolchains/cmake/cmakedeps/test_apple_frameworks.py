import platform
import re
import textwrap

import pytest

from conans.client.tools.env import environment_append
from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient


@pytest.fixture
def client():
    lib_ref = ConanFileReference.loads("foolib/1.0")
    lib_conanfile = textwrap.dedent("""
        from conans import ConanFile

        class FooLib(ConanFile):
            def package_info(self):
                self.cpp_info.frameworks.extend(['Foundation', 'CoreServices', 'CoreFoundation'])
    """)

    t = TestClient()
    t.save({'conanfile.py': lib_conanfile})
    t.run("create . {}@".format(lib_ref))
    return t


app_conanfile = textwrap.dedent("""
    from conans import ConanFile, CMake

    class App(ConanFile):
        requires = "foolib/1.0"
        generators = "CMakeDeps", "CMakeToolchain"
        settings = "build_type",  # cmake_multi doesn't work without build_type

        def build(self):
            cmake = CMake(self)
            cmake.configure()
""")

@pytest.mark.skipif(platform.system() != "Darwin", reason="Only OSX")
@pytest.mark.tool_cmake(version="3.19")
def test_apple_framework_xcode(client):
    app_cmakelists = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(Testing CXX)
        find_package(foolib REQUIRED)
        message(">>> foolib_FRAMEWORKS_FOUND_DEBUG: ${foolib_FRAMEWORKS_FOUND_DEBUG}")
        message(">>> foolib_FRAMEWORKS_FOUND_RELEASE: ${foolib_FRAMEWORKS_FOUND_RELEASE}")
    """)

    client.save({'conanfile.py': app_conanfile,
                 'CMakeLists.txt': app_cmakelists})
    with environment_append({"CONAN_CMAKE_GENERATOR": "Xcode"}):
        client.run("install . -s build_type=Release")
        client.run("install . -s build_type=Debug")
        client.run("build .")
        assert "/System/Library/Frameworks/Foundation.framework;" in client.out
        assert "/System/Library/Frameworks/CoreServices.framework;" in client.out
        assert "/System/Library/Frameworks/CoreFoundation.framework" in client.out


conanfile = textwrap.dedent("""
            from conans import ConanFile
            from conans import tools
            from conan.tools.cmake import CMake, CMakeToolchain

            class AppleframeworkConan(ConanFile):
                settings = "os", "compiler", "build_type", "arch"
                generators = "CMakeDeps", "CMakeToolchain"
                exports_sources = "src/*"
                name = "mylibrary"
                version = "1.0"

                def layout(self):
                    self.folders.source = "src"

                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
                    cmake.build()
                    cmake.install()
                    self.run("otool -L '%s/hello.framework/hello'" % self.build_folder)
                    self.run("otool -L '%s/hello.framework/hello'" % self.package_folder)

                def package_info(self):
                    self.cpp_info.frameworkdirs.append(self.package_folder)
                    self.cpp_info.frameworks.append("hello")
                    self.cpp_info.includedirs = []
            """)
cmake = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.15)
            project(MyHello CXX)

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

@pytest.mark.skipif(platform.system() != "Darwin", reason="Only OSX")
@pytest.mark.parametrize("settings",
                         [('',),
                          ('-pr:b default -s os=iOS -s os.sdk=iphoneos -s os.version=10.0 -s arch=armv8',),
                          ("-pr:b default -s os=tvOS -s os.sdk=appletvos -s os.version=11.0 -s arch=armv8",)])
def test_apple_own_framework_cross_build(settings):
    client = TestClient()

    test_cmake = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(Testing CXX)

        find_package(mylibrary REQUIRED)

        add_executable(timer timer.cpp)
        target_link_libraries(timer mylibrary::mylibrary)
    """)

    test_conanfile = textwrap.dedent("""
        from conans import ConanFile, tools
        from conan.tools.cmake import CMake, CMakeToolchain

        class TestPkg(ConanFile):
            generators = "CMakeDeps", "CMakeToolchain"
            settings = "os", "arch", "compiler", "build_type"

            def build(self):
                self.output.warn("Building test package at: {}".format(self.build_folder))
                cmake = CMake(self)
                cmake.configure()
                cmake.build()

            def test(self):
                if not tools.cross_building(self):
                    self.run("timer", run_environment=True)
        """)

    client.save({'conanfile.py': conanfile,
                 "src/CMakeLists.txt": cmake,
                 "src/hello.h": hello_h,
                 "src/hello.cpp": hello_cpp,
                 "src/Info.plist": infoplist,
                 "test_package/conanfile.py": test_conanfile,
                 'test_package/CMakeLists.txt': test_cmake,
                 "test_package/timer.cpp": timer_cpp})
    client.run("create . %s" % settings)
    if not len(settings):
        assert "Hello World Release!" in client.out


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only OSX")
@pytest.mark.tool_cmake(version="3.19")
def test_apple_own_framework_cmake_deps():
    client = TestClient()

    test_cmake = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(Testing CXX)
        message(STATUS "CMAKE_BINARY_DIR ${CMAKE_BINARY_DIR}")
        find_package(mylibrary REQUIRED)
        message(">>> MYLIBRARY_FRAMEWORKS_FOUND_DEBUG: ${MYLIBRARY_FRAMEWORKS_FOUND_DEBUG}")
        message(">>> MYLIBRARY_FRAMEWORKS_FOUND_RELEASE: ${MYLIBRARY_FRAMEWORKS_FOUND_RELEASE}")
        add_executable(timer timer.cpp)
        target_link_libraries(timer mylibrary::mylibrary)
    """)

    test_conanfile = textwrap.dedent("""
        import os
        from conans import ConanFile
        from conan.tools.cmake import CMake

        class TestPkg(ConanFile):
            generators = "CMakeDeps", "CMakeToolchain"
            name = "app"
            version = "1.0"
            requires = "mylibrary/1.0"
            exports_sources = "CMakeLists.txt", "timer.cpp"
            settings = "build_type",

            def layout(self):
                self.folders.build = str(self.settings.build_type)

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()

            def test(self):
                self.run(os.path.join(str(self.settings.build_type), "timer"), run_environment=True)
        """)
    client.save({'conanfile.py': conanfile,
                 "src/CMakeLists.txt": cmake,
                 "src/hello.h": hello_h,
                 "src/hello.cpp": hello_cpp,
                 "src/Info.plist": infoplist})
    client.run("export . mylibrary/1.0@")
    client.run("create . mylibrary/1.0@ -s build_type=Debug")
    client.run("create . mylibrary/1.0@ -s build_type=Release")

    profile = textwrap.dedent("""
        include(default)
        [conf]
        tools.cmake.cmaketoolchain:generator=Xcode
        """)
    client.save({"conanfile.py": test_conanfile,
                 'CMakeLists.txt': test_cmake,
                 "timer.cpp": timer_cpp,
                 "profile": profile})

    client.run("install . -s build_type=Debug -pr=profile")
    client.run("install . -s build_type=Release -pr=profile")
    client.run("test . mylibrary/1.0@  -pr=profile")
    assert "Hello World Release!" in client.out
    client.run("test . mylibrary/1.0@ -s build_type=Debug  -pr=profile")
    assert "Hello World Debug!" in client.out


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only OSX")
def test_apple_own_framework_cmake_find_package_multi():
    client = TestClient()

    test_cmake = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
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
            generators = "CMakeDeps", "CMakeToolchain"
            settings = "build_type",
            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()
            def test(self):
                self.run("bin/timer", run_environment=True)
        """)
    client.save({'conanfile.py': conanfile,
                 "src/CMakeLists.txt": cmake,
                 "src/hello.h": hello_h,
                 "src/hello.cpp": hello_cpp,
                 "src/Info.plist": infoplist,
                 "test_package/conanfile.py": test_conanfile,
                 'test_package/CMakeLists.txt': test_cmake,
                 "test_package/timer.cpp": timer_cpp})
    client.run("create .")
    assert "Hello World Release!" in client.out


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only OSX")
def test_component_uses_apple_framework():
    conanfile_py = textwrap.dedent("""
from conans import ConanFile, tools
from conan.tools.cmake import CMake


class HelloConan(ConanFile):
    name = "hello"
    description = "example"
    topics = ("conan",)
    url = "https://github.com/conan-io/conan-center-index"
    homepage = "https://www.example.com"
    license = "MIT"
    exports_sources = ["hello.cpp", "hello.h", "CMakeLists.txt"]
    generators = "CMakeDeps", "CMakeToolchain"
    settings = "os", "arch", "compiler", "build_type"

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()
        cmake.install()

    def package_info(self):
        self.cpp_info.set_property("cmake_file_name", "HELLO")
        self.cpp_info.components["libhello"].set_property("cmake_target_name", "hello::libhello")

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
cmake_minimum_required(VERSION 3.15)
project(hello)
include(GNUInstallDirs)
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
    test_conanfile_py = textwrap.dedent("""
import os
from conans import ConanFile, tools
from conan.tools.cmake import CMake

class TestPackageConan(ConanFile):
    settings = "os", "compiler", "build_type", "arch"
    generators = "CMakeDeps", "CMakeToolchain"

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()

    def test(self):
        if not tools.cross_building(self.settings):
            self.run("test_package", run_environment=True)
        """)
    test_test_package_cpp = textwrap.dedent("""
#include "hello.h"

int main()
{
    hello_api();
}
        """)
    test_cmakelists_txt = textwrap.dedent("""
cmake_minimum_required(VERSION 3.15)
project(test_package)

find_package(HELLO REQUIRED CONFIG)

add_executable(${PROJECT_NAME} test_package.cpp)
target_link_libraries(${PROJECT_NAME} hello::libhello)
        """)
    t = TestClient()
    t.save({'conanfile.py': conanfile_py,
            'hello.cpp': hello_cpp,
            'hello.h': hello_h,
            'CMakeLists.txt': cmakelists_txt,
            'test_package/conanfile.py': test_conanfile_py,
            'test_package/CMakeLists.txt': test_cmakelists_txt,
            'test_package/test_package.cpp': test_test_package_cpp})
    t.run("create . hello/1.0@")


@pytest.mark.tool_cmake(version="3.19")
@pytest.mark.skipif(platform.system() != "Darwin", reason="Only OSX")
def test_apple_different_components_but_same_framework_names():
    """
    Testing issue about incorrect path found for a different
    component with the same framework names

    Note: this test is only using CMake tool but it's not compiling anything

    Issue: https://github.com/conan-io/conan/pull/12088
    """
    client = TestClient()

    conanfile = textwrap.dedent("""
    import os

    from conan import ConanFile
    from conan.tools.files import mkdir, save

    class HelloConan(ConanFile):
        name = "hello"
        version = "1.0"
        settings = "os", "build_type"

        def package(self):
            mkdir(self, os.path.join(self.package_folder, "ComponentA"))
            mkdir(self, os.path.join(self.package_folder, "ComponentB"))
            save(self, os.path.join(self.package_folder, "ComponentA", "libComponent.a"), b"#whatever")
            save(self, os.path.join(self.package_folder, "ComponentB", "libComponent.a"), b"#whatever")

        def package_info(self):
            self.cpp_info.components["ComponentA"].frameworkdirs = [os.path.join(self.package_folder, "ComponentA")]
            self.cpp_info.components["ComponentA"].frameworks = ["Component"]
            self.cpp_info.components["ComponentA"].includedirs = []
            self.cpp_info.components["ComponentB"].frameworkdirs = [os.path.join(self.package_folder, "ComponentB")]
            self.cpp_info.components["ComponentB"].frameworks = ["Component"]
            self.cpp_info.components["ComponentB"].includedirs = []
    """)
    test_cmakelist = textwrap.dedent("""
    cmake_minimum_required(VERSION 3.15)
    project(PackageTest CXX)

    find_package(hello CONFIG REQUIRED)

    message("hello::ComponentA FRAMEWORK_DIRS: ${hello_hello_ComponentA_FRAMEWORK_DIRS_RELEASE}")
    message("hello::ComponentA FRAMEWORKS_FOUND: ${hello_hello_ComponentA_FRAMEWORKS_FOUND_RELEASE}")
    message("hello::ComponentB FRAMEWORK_DIRS: ${hello_hello_ComponentB_FRAMEWORK_DIRS_RELEASE}")
    message("hello::ComponentB FRAMEWORKS_FOUND: ${hello_hello_ComponentB_FRAMEWORKS_FOUND_RELEASE}")
    """)
    test_conanfile = textwrap.dedent("""
    from conan import ConanFile
    from conan.tools.cmake import CMake

    class HelloTestConan(ConanFile):
        settings = "os", "build_type"
        generators = "CMakeDeps", "CMakeToolchain"
        apply_env = False
        test_type = "explicit"

        def requirements(self):
            self.requires(self.tested_reference_str)

        def build(self):
            cmake = CMake(self)
            cmake.configure()
            cmake.build()

        def test(self):
            pass
    """)
    client.save({'conanfile.py': conanfile,
                 "test_package/conanfile.py": test_conanfile,
                 'test_package/CMakeLists.txt': test_cmakelist})
    client.run("create . -s build_type=Release")
    # Checking that each Component has its own Framework
    assert re.search(r"hello::ComponentA\D+FRAMEWORKS_FOUND:.*/ComponentA/libComponent\.a", str(client.out), re.MULTILINE)
    assert re.search(r"hello::ComponentB\D+FRAMEWORKS_FOUND:.*/ComponentB/libComponent\.a", str(client.out), re.MULTILINE)
