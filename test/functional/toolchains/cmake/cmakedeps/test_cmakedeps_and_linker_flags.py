import os
import platform
import textwrap

import pytest

from conan.test.assets.sources import gen_function_cpp, gen_function_h
from conan.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() != "Linux", reason="Only Linux")
@pytest.mark.tool("cmake")
def test_shared_link_flags():
    """
    Testing CMakeDeps and linker flags injection

    Issue: https://github.com/conan-io/conan/issues/9936
    """
    conanfile = textwrap.dedent("""
    from conan import ConanFile
    from conan.tools.cmake import CMake, cmake_layout


    class HelloConan(ConanFile):
        name = "hello"
        version = "1.0"
        settings = "os", "compiler", "build_type", "arch"
        options = {"shared": [True, False]}
        default_options = {"shared": False}
        exports_sources = "CMakeLists.txt", "src/*", "include/*"
        generators = "CMakeDeps", "CMakeToolchain"

        def layout(self):
            cmake_layout(self)

        def build(self):
            cmake = CMake(self)
            cmake.configure()
            cmake.build()

        def package(self):
            cmake = CMake(self)
            cmake.install()

        def package_info(self):
            self.cpp_info.libs = ["hello"]
            self.cpp_info.sharedlinkflags = ["-z now", "-z relro"]
            self.cpp_info.exelinkflags = ["-z now", "-z relro"]
    """)

    client = TestClient()
    client.run("new cmake_lib -d name=hello -d version=1.0")
    client.save({"conanfile.py": conanfile})
    client.run("create .")
    host_arch = client.get_default_host_profile().settings['arch']
    build_folder = client.created_test_build_folder("hello/1.0")
    t = os.path.join("test_package", build_folder, "generators",
                     f"hello-release-{host_arch}-data.cmake")
    target_data_cmake_content = client.load(t)
    assert 'set(hello_SHARED_LINK_FLAGS_RELEASE "-z now;-z relro")' in target_data_cmake_content
    assert 'set(hello_EXE_LINK_FLAGS_RELEASE "-z now;-z relro")' in target_data_cmake_content
    assert "hello/1.0: Hello World Release!" in client.out


def test_not_mixed_configurations():
    # https://github.com/conan-io/conan/issues/11852

    client = TestClient()
    client.run("new cmake_lib -d name=foo  -d version=1.0")

    conanfile = client.load("conanfile.py")
    conanfile.replace("package_info(self)", "invalid(self)")
    conanfile += """
    def package_info(self):
        self.cpp_info.libs = ["foo" if self.settings.build_type == "Release" else "foo_d"]
    """

    cmake = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.15)
            project(foo CXX)

            add_library(foo "src/foo.cpp")
            target_include_directories(foo PUBLIC include)
            set_target_properties(foo PROPERTIES PUBLIC_HEADER "include/foo.h")

            # Different name for Release or Debug
            set_target_properties(foo PROPERTIES OUTPUT_NAME_DEBUG foo_d)
            set_target_properties(foo PROPERTIES OUTPUT_NAME_RELEASE foo)
            install(TARGETS foo)
    """)

    client.save({"CMakeLists.txt": cmake, "conanfile.py": conanfile})
    client.run("create .")
    client.run("create . -s build_type=Debug")
    if platform.system() != "Windows":
        assert "libfoo_d.a" in client.out  # Just to make sure we built the foo_d

    # Now create a consumer of foo with CMakeDeps locally
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMakeToolchain, CMake, cmake_layout

        class ConsumerConan(ConanFile):
            name = "consumer"
            version = "1.0"
            settings = "os", "compiler", "build_type", "arch"
            requires = "foo/1.0"
            generators = "CMakeDeps"

            def layout(self):
                cmake_layout(self)

            def generate(self):
                tc = CMakeToolchain(self)
                tc.cache_variables["CMAKE_VERBOSE_MAKEFILE:BOOL"] = "ON"
                tc.generate()

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()

            """)
    cmake = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.15)
            project(consumer CXX)

            find_package(foo)

            add_executable(consumer src/consumer.cpp)
            target_include_directories(consumer PUBLIC include)
            target_link_libraries(consumer foo::foo)

            set_target_properties(consumer PROPERTIES PUBLIC_HEADER "include/consumer.h")""")
    consumer_cpp = gen_function_cpp(name="main", includes=["foo"], calls=["foo"])
    consumer_h = gen_function_h(name="consumer")

    client.save({"conanfile.py": conanfile, "CMakeLists.txt": cmake,
                 "src/consumer.cpp": consumer_cpp, "src/consumer.h": consumer_h})

    client.run("install . -s build_type=Debug")
    client.run("install . -s build_type=Release")
    # With the bug, this build only fail on windows
    client.run("build .")

    # But we inspect the output for Macos/Linux to check that the library is not linked
    if platform.system() != "Windows":
        assert "libfoo_d.a" not in client.out
        assert "libfoo.a" in client.out
