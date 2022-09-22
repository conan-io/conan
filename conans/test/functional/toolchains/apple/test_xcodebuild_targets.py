import platform
import textwrap

import pytest

from conans.test.utils.tools import TestClient

xcode_project = textwrap.dedent("""
    name: HelloLibrary
    targets:
      hello-static:
        type: library.static
        platform: macOS
        sources:
          - src
        configFiles:
          Debug: static.xcconfig
          Release: static.xcconfig
      hello-dynamic:
        type: library.dynamic
        platform: macOS
        sources:
          - src
        configFiles:
          Debug: dynamic.xcconfig
          Release: dynamic.xcconfig

    """)

hello_cpp = textwrap.dedent("""
    #include "hello.hpp"
    #include <iostream>

    void hellofunction(){
        #ifndef DEBUG
        std::cout << "Hello Release!" << std::endl;
        #else
        std::cout << "Hello Debug!" << std::endl;
        #endif
    }
    """)

hello_hpp = textwrap.dedent("""
    #ifndef hello_hpp
    #define hello_hpp

    void hellofunction();

    #endif /* hello_hpp */
    """)

test = textwrap.dedent("""
    import os

    from conan import ConanFile
    from conan.tools.cmake import CMake, cmake_layout
    from conan.tools.build import cross_building


    class HelloTestConan(ConanFile):
        settings = "os", "compiler", "build_type", "arch"
        # VirtualBuildEnv and VirtualRunEnv can be avoided if "tools.env.virtualenv:auto_use" is defined
        # (it will be defined in Conan 2.0)
        generators = "CMakeDeps", "CMakeToolchain", "VirtualBuildEnv", "VirtualRunEnv"
        apply_env = False
        test_type = "explicit"
        options = {"shared": [True, False], "fPIC": [True, False]}
        default_options = {"shared": False, "fPIC": True}

        def requirements(self):
            self.requires(self.tested_reference_str)

        def build(self):
            cmake = CMake(self)
            cmake.configure()
            cmake.build()

        def layout(self):
            cmake_layout(self)

        def test(self):
            if not cross_building(self):
                cmd = os.path.join(self.cpp.build.bindirs[0], "example")
                self.run(cmd, env="conanrun")
                if self.options.shared:
                    self.run("otool -l {}".format(os.path.join(self.cpp.build.bindirs[0], "example")))
                else:
                    self.run("nm {}".format(os.path.join(self.cpp.build.bindirs[0], "example")))
    """)

cmakelists = textwrap.dedent("""
    cmake_minimum_required(VERSION 3.15)
    project(PackageTest CXX)

    find_package(hello CONFIG REQUIRED)

    add_executable(example src/example.cpp)
    target_link_libraries(example hello::hello)
    """)

test_src = textwrap.dedent("""
    #include "hello.hpp"

    int main() {
        hellofunction();
    }
    """)

conanfile = textwrap.dedent("""
    import os
    from conan import ConanFile
    from conan.tools.apple import XcodeBuild
    from conan.tools.files import copy

    class HelloLib(ConanFile):
        name = "hello"
        version = "1.0"
        settings = "os", "compiler", "build_type", "arch"
        generators = "XcodeToolchain"
        exports_sources = "HelloLibrary.xcodeproj/*", "src/*", "static.xcconfig", "dynamic.xcconfig"
        options = {"shared": [True, False], "fPIC": [True, False]}
        default_options = {"shared": False, "fPIC": True}

        def build(self):
            xcode = XcodeBuild(self)
            if self.options.shared:
                xcode.build("HelloLibrary.xcodeproj", target="hello-dynamic")
            else:
                xcode.build("HelloLibrary.xcodeproj", target="hello-static")

        def package(self):
            name = "hello-dynamic.dylib" if self.options.shared else "libhello-static.a"
            copy(self, "build/{}/{}".format(self.settings.build_type, name),
                 src=self.build_folder, dst=os.path.join(self.package_folder, "lib"), keep_path=False)
            copy(self, "*/*.hpp", src=self.build_folder, dst=os.path.join(self.package_folder, "include"), keep_path=False)

        def package_info(self):
            self.cpp_info.libs = ["hello-{}".format("dynamic.dylib" if self.options.shared else "static")]
    """)

static_xcconfig = textwrap.dedent("""
    #include \"conan_config.xcconfig\"
    LD_DYLIB_INSTALL_NAME = @rpath/libhello-static.dylib
""")

dynamic_xcconfig = textwrap.dedent("""
    #include \"conan_config.xcconfig\"
    LD_DYLIB_INSTALL_NAME = @rpath/hello-dynamic.dylib
""")


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only for MacOS")
@pytest.mark.tool_xcodebuild
def test_shared_static_targets():
    """
    The pbxproj has defined two targets, one for static and one for dynamic libraries, in the
    XcodeBuild build helper we pass the target we want to build depending on the shared option
    """
    client = TestClient()
    client.save({"conanfile.py": conanfile,
                 "src/hello.cpp": hello_cpp,
                 "src/hello.hpp": hello_hpp,
                 "project.yml": xcode_project,
                 "test_package/conanfile.py": test,
                 "test_package/src/example.cpp": test_src,
                 "test_package/CMakeLists.txt": cmakelists,
                 "conan_config.xcconfig": "",
                 "static.xcconfig": static_xcconfig,
                 "dynamic.xcconfig": dynamic_xcconfig})

    client.run_command("xcodegen generate")

    client.run("create . -o *:shared=True -tf None")
    assert "Packaged 1 '.dylib' file: hello-dynamic.dylib" in client.out
    client.run("test test_package hello/1.0@ -o *:shared=True")
    assert "@rpath/hello-dynamic.dylib" in client.out

    client.run("create . -tf None")
    assert "Packaged 1 '.a' file: libhello-static.a" in client.out
    client.run("test test_package hello/1.0@")
    # check the symbol hellofunction in in the executable
    assert "hellofunction" in client.out
