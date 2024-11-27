import platform
import textwrap

import pytest

from conan.test.assets.sources import gen_function_cpp
from conan.test.utils.tools import TestClient


@pytest.fixture
def client():
    lib_conanfile = textwrap.dedent("""
        from conan import ConanFile

        class FooLib(ConanFile):
            name = "foolib"
            version = "1.0"

            def package_info(self):
                self.cpp_info.frameworks.extend(['Foundation', 'CoreServices', 'CoreFoundation'])
    """)

    t = TestClient()
    t.save({'conanfile.py': lib_conanfile})
    t.run("create .")
    return t


app_conanfile = textwrap.dedent("""
    from conan import ConanFile
    from conan.tools.cmake import CMake

    class App(ConanFile):
        requires = "foolib/1.0"
        generators = "CMakeDeps", "CMakeToolchain"
        settings = "build_type", "os", "arch"

        def build(self):
            cmake = CMake(self)
            cmake.configure()
""")


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only OSX")
@pytest.mark.tool("cmake", "3.19")
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

    client.run("build . -c tools.cmake.cmaketoolchain:generator=Xcode")
    assert "/System/Library/Frameworks/Foundation.framework;" in client.out
    assert "/System/Library/Frameworks/CoreServices.framework;" in client.out
    assert "/System/Library/Frameworks/CoreFoundation.framework" in client.out


conanfile = textwrap.dedent("""
            from conan import ConanFile
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


@pytest.mark.tool("cmake")
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
        import os
        from conan import ConanFile
        from conan.tools.cmake import CMake, CMakeToolchain, CMakeDeps, cmake_layout
        from conan.tools.build import cross_building

        class TestPkg(ConanFile):
            generators = "CMakeToolchain"
            settings = "os", "arch", "compiler", "build_type"

            def layout(self):
                cmake_layout(self)

            def requirements(self):
                self.requires(self.tested_reference_str)
                self.tool_requires(self.tested_reference_str)

            def generate(self):
                cmake = CMakeDeps(self)
                cmake.build_context_activated = ["mylibrary"]
                cmake.build_context_suffix = {"mylibrary": "_BUILD"}
                cmake.generate()

            def build(self):
                self.output.warning("Building test package at: {}".format(self.build_folder))
                cmake = CMake(self)
                cmake.configure()
                cmake.build()

            def test(self):
                if not cross_building(self):
                    cmd = os.path.join(self.cpp.build.bindirs[0], "timer")
                    self.run(cmd, env="conanrunenv")
        """)

    client.save({'conanfile.py': conanfile,
                 "src/CMakeLists.txt": cmake,
                 "src/hello.h": hello_h,
                 "src/hello.cpp": hello_cpp,
                 "src/Info.plist": infoplist,
                 "test_package/conanfile.py": test_conanfile,
                 'test_package/CMakeLists.txt': test_cmake,
                 "test_package/timer.cpp": timer_cpp})
    # First build it as build_require in the build-context, no testing
    # the UX could be improved, but the simplest could be:
    #  - Have users 2 test_packages, one for the host and other for the build, with some naming
    #    convention. CI launches one after the other if found
    client.run("create . %s -tf=\"\" --build-require" % settings)
    client.run("create . %s" % settings)
    if not len(settings):
        assert "Hello World Release!" in client.out


@pytest.mark.xfail(reason="run_environment=True no longer works")
@pytest.mark.skipif(platform.system() != "Darwin", reason="Only OSX")
@pytest.mark.tool("cmake", "3.19")
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
        from conan import ConanFile
        from conan.tools.cmake import CMake

        class TestPkg(ConanFile):
            generators = "CMakeToolchain"
            name = "app"
            version = "1.0"
            requires = "mylibrary/1.0"
            exports_sources = "CMakeLists.txt", "timer.cpp"
            settings = "os", "arch", "compiler", "build_type"

            def requirements(self):
                self.tool_requires(self.tested_reference_str)

            def generate(self):
                cmake = CMakeDeps(self)
                cmake.build_context_activated = ["mylibrary"]
                cmake.build_context_suffix = {"mylibrary": "_BUILD"}
                cmake.generate()

            def layout(self):
                self.folders.build = str(self.settings.build_type)

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()

            def test(self):
                self.run(os.path.join(str(self.settings.build_type), "timer"), env="conanrunenv")
        """)
    client.save({'conanfile.py': conanfile,
                 "src/CMakeLists.txt": cmake,
                 "src/hello.h": hello_h,
                 "src/hello.cpp": hello_cpp,
                 "src/Info.plist": infoplist})
    client.run("export . --name=mylibrary --version=1.0")
    client.run("create . --name=mylibrary --version=1.0 -s build_type=Debug")
    client.run("create . --name=mylibrary --version=1.0 -s build_type=Release")

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
    client.run("test . mylibrary/1.0@ -s:b build_type=Debug  -pr=profile")
    assert "Hello World Debug!" in client.out


@pytest.mark.tool("cmake")
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
        from conan import ConanFile
        from conan.tools.cmake import CMake
        class TestPkg(ConanFile):
            generators = "CMakeDeps", "CMakeToolchain"
            settings = "build_type", "os", "arch"

            def requirements(self):
                self.requires(self.tested_reference_str)

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()
            def test(self):
                self.run("bin/timer", env="conanrunenv")
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


@pytest.mark.tool("cmake", "3.19")
@pytest.mark.skipif(platform.system() != "Darwin", reason="Only OSX")
def test_component_uses_apple_framework():
    conanfile_py = textwrap.dedent("""
from conan import ConanFile, tools
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
        # We need to add the information about the lib/include directories to be able to find them
        self.cpp_info.components["libhello"].libdirs = ["lib"]
        self.cpp_info.components["libhello"].includedirs = ["include"]

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
from conan import ConanFile, tools
from conan.tools.cmake import CMake, CMakeToolchain, CMakeDeps
from conan.tools.build import cross_building


class TestPackageConan(ConanFile):
    settings = "os", "compiler", "build_type", "arch"
    generators = "CMakeToolchain"

    def requirements(self):
        self.requires(self.tested_reference_str)
        self.tool_requires(self.tested_reference_str)

    def generate(self):
        cmake = CMakeDeps(self)
        cmake.build_context_activated = ["hello"]
        cmake.build_context_suffix = {"hello": "_BUILD"}
        cmake.generate()

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()

    def test(self):
        if not cross_building(self):
            self.run("./test_package", env="conanrunenv")
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
    t.run("create . --name=hello --version=1.0")


@pytest.mark.tool("cmake")
@pytest.mark.skipif(platform.system() != "Darwin", reason="Only OSX")
def test_iphoneos_crossbuild():
    profile = textwrap.dedent("""
        include(default)
        [settings]
        os=iOS
        os.version=12.0
        os.sdk=iphoneos
        arch=armv8
    """).format()

    client = TestClient(path_with_spaces=False)
    client.save({"ios-armv8": profile}, clean_first=True)
    client.run("new cmake_lib -d name=hello -d version=0.1")
    client.run("create . --profile:build=default --profile:host=ios-armv8 -tf=\"\"")

    main = gen_function_cpp(name="main", includes=["hello"], calls=["hello"])
    # FIXME: The crossbuild for iOS etc is failing with find_package because cmake ignore the
    #        cmake_prefix_path to point only to the Frameworks of the system. The only fix found
    #        would require to introduce something like "set (mylibrary_DIR "${CMAKE_BINARY_DIR}")"
    #        at the toolchain (but it would require the toolchain to know about the deps)
    #        https://stackoverflow.com/questions/65494246/cmakes-find-package-ignores-the-paths-option-when-building-for-ios#
    cmakelists = textwrap.dedent("""
    cmake_minimum_required(VERSION 3.15)
    project(MyApp CXX)
    set(hello_DIR "${CMAKE_BINARY_DIR}")
    find_package(hello)
    add_executable(main main.cpp)
    target_link_libraries(main hello::hello)
    """)

    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMake

        class TestConan(ConanFile):
            requires = "hello/0.1"
            settings = "os", "compiler", "arch", "build_type"
            exports_sources = "CMakeLists.txt", "main.cpp"
            generators = "CMakeDeps", "CMakeToolchain"

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()
        """)

    client.save({"conanfile.py": conanfile,
                 "CMakeLists.txt": cmakelists,
                 "main.cpp": main,
                 "ios-armv8": profile}, clean_first=True)
    client.run("install . --profile:build=default --profile:host=ios-armv8")
    client.run("build . --profile:build=default --profile:host=ios-armv8")
    main_path = "./main.app/main"
    client.run_command("lipo -info {}".format(main_path))
    assert "Non-fat file" in client.out
    assert "is architecture: arm64" in client.out
    client.run_command(f"vtool -show-build {main_path}")
    assert "platform IOS" in client.out
    assert "minos 12.0" in client.out
