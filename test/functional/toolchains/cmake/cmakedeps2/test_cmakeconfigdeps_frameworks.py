import platform
import textwrap

import pytest

from conan.internal.model.pkg_type import PackageType
from conan.test.utils.tools import TestClient

new_value = "will_break_next"


@pytest.mark.parametrize("shared", [True, False])
@pytest.mark.tool("cmake")
@pytest.mark.skipif(platform.system() != "Darwin", reason="Only OSX")
def test_osx_frameworks(shared):
    """
    Testing custom package frameworks + system frameworks
    """
    cmakelists = textwrap.dedent("""
    cmake_minimum_required(VERSION 3.15)
    project(MyFramework CXX)

    add_library(MyFramework frame.cpp frame.h)

    set_target_properties(MyFramework PROPERTIES
      FRAMEWORK TRUE
      FRAMEWORK_VERSION C # Version "A" is macOS convention
      MACOSX_FRAMEWORK_IDENTIFIER MyFramework
      PUBLIC_HEADER frame.h
    )

    install(TARGETS MyFramework
      FRAMEWORK DESTINATION .)
    """)
    frame_cpp = textwrap.dedent("""
    #include "frame.h"
    #include <iostream>
    #include <CoreFoundation/CoreFoundation.h>

    void greet() {
        CFTypeRef keys[] = {CFSTR("key")};
        CFTypeRef values[] = {CFSTR("value")};
        CFDictionaryRef dict = CFDictionaryCreate(kCFAllocatorDefault, keys, values, sizeof(keys) / sizeof(keys[0]),
                        &kCFTypeDictionaryKeyCallBacks, &kCFTypeDictionaryValueCallBacks);
        if (dict)
            CFRelease(dict);
        std::cout << "Hello from MyFramework!" << std::endl;
    }
    """)
    frame_h = textwrap.dedent("""
    #pragma once
    #include <vector>
    #include <string>
    void greet();
    """)
    cpp_info_type = PackageType.SHARED if shared else PackageType.STATIC
    conanfile = textwrap.dedent(f"""
    import os
    from conan import ConanFile
    from conan.tools.cmake import CMake

    class MyFramework(ConanFile):
        name = "frame"
        version = "1.0"
        settings = "os", "arch", "compiler", "build_type"
        languages = ["C++"]
        package_type = "{'static-library' if shared else 'shared-library'}"
        exports_sources = ["frame.cpp", "frame.h", "CMakeLists.txt"]
        generators = "CMakeToolchain"

        def build(self):
            cmake = CMake(self)
            cmake.configure()
            cmake.build()

        def package(self):
            cmake = CMake(self)
            cmake.install()

        def package_info(self):
            self.cpp_info.type = "{cpp_info_type}"
            self.cpp_info.package_framework = "MyFramework"
            self.cpp_info.location = os.path.join(self.package_folder, "MyFramework.framework", "MyFramework")
            # Using also a system framework
            self.cpp_info.frameworks = ["CoreFoundation"]
    """)
    test_main_cpp = textwrap.dedent("""
    #include <MyFramework/frame.h>
    int main() {
        greet();
    }
    """)
    test_conanfile = textwrap.dedent("""
    import os
    from conan import ConanFile
    from conan.tools.cmake import CMake, cmake_layout
    from conan.tools.build import can_run

    class LibTestConan(ConanFile):
        settings = "os", "compiler", "build_type", "arch"
        generators = "CMakeConfigDeps", "CMakeToolchain"

        def requirements(self):
            self.requires(self.tested_reference_str)

        def build(self):
            cmake = CMake(self)
            cmake.configure()
            cmake.build()

        def layout(self):
            cmake_layout(self)

        def test(self):
            if can_run(self):
                cmd = os.path.join(self.cpp.build.bindir, "example")
                self.run(cmd, env="conanrun")
    """)
    test_cmakelists = textwrap.dedent("""
    cmake_minimum_required(VERSION 3.15)
    project(PackageTest CXX)
    find_package(frame CONFIG REQUIRED)
    add_executable(example main.cpp)
    target_link_libraries(example frame::frame)
    """)
    client = TestClient()
    client.save({
        'test_package/main.cpp': test_main_cpp,
        'test_package/CMakeLists.txt': test_cmakelists,
        'test_package/conanfile.py': test_conanfile,
        'CMakeLists.txt': cmakelists,
        'frame.cpp': frame_cpp,
        'frame.h': frame_h,
        'conanfile.py': conanfile
    })
    client.run(f"create . -c tools.cmake.cmakedeps:new={new_value} -o '*:shared={shared}'")
    assert "Hello from MyFramework!" in client.out
