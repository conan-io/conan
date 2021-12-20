import platform
import textwrap

import pytest

from conans.test.utils.tools import TestClient


@pytest.mark.tool_cmake
@pytest.mark.parametrize("package", ["hello", "ZLIB"])
@pytest.mark.parametrize("find_package", ["module", "config"])
@pytest.mark.parametrize(
    "host",
    [
        "native",
        pytest.param(
            "cross_build_iOS", marks=pytest.mark.skipif(
                platform.system() != "Darwin", reason="OSX only",
            ),
        ),
    ],
)
def test_cmaketoolchain_path_find_package(package, find_package, host):
    """Test with user "Hello" and also ZLIB one, to check that package ZLIB
    has priority over the CMake system one
    """
    client = TestClient()

    cross_build = "cross_build" in host
    if cross_build:
        host_profile = "ios12.0-armv8"
        profile_content = textwrap.dedent("""
            include(default)
            [settings]
            os=iOS
            os.version=12.0
            arch=armv8
        """)
        client.save({host_profile: profile_content})

    conanfile = textwrap.dedent("""
        from conans import ConanFile
        class TestConan(ConanFile):
            exports = "*"
            def layout(self):
                pass
            def package(self):
                self.copy(pattern="*")
            def package_info(self):
                self.cpp_info.builddirs.append("cmake")
        """)
    find = textwrap.dedent("""
        SET({package}_FOUND 1)
        MESSAGE("HELLO FROM THE {package} FIND PACKAGE!")
        """).format(package=package)

    filename = "{}Config.cmake" if find_package == "config" else "Find{}.cmake"
    filename = filename.format(package)
    client.save({"conanfile.py": conanfile, "cmake/{}".format(filename): find})
    client.run("create . {}/0.1@{}".format(
        package,
        " -pr:b default -pr:h {}".format(host_profile) if cross_build else "",
    ))

    consumer = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(MyHello CXX)
        find_package({package} REQUIRED)
        """).format(package=package)

    client.save({"CMakeLists.txt": consumer}, clean_first=True)
    if cross_build:
        client.save({host_profile: profile_content})
    client.run("install {}/0.1@ -g CMakeToolchain{}".format(
        package,
        " -pr:b default -pr:h {}".format(host_profile) if cross_build else "",
    ))
    with client.chdir("build"):
        client.run_command("cmake .. -DCMAKE_TOOLCHAIN_FILE=../conan_toolchain.cmake")
    assert "Conan: Target declared" not in client.out
    assert "HELLO FROM THE {package} FIND PACKAGE!".format(package=package) in client.out

    # If using the CMakeDeps generator, the in-package .cmake will be ignored
    client.run("install {}/0.1@ -g CMakeToolchain -g CMakeDeps{}".format(
        package,
        " -pr:b default -pr:h {}".format(host_profile) if cross_build else "",
    ))
    with client.chdir("build2"):  # A clean folder, not the previous one, CMake cache doesnt affect
        client.run_command("cmake .. -DCMAKE_TOOLCHAIN_FILE=../conan_toolchain.cmake")
    assert "Conan: Target declared '{package}::{package}'".format(package=package) in client.out
    assert "HELLO FROM THE {package} FIND PACKAGE!".format(package=package) not in client.out


@pytest.mark.tool_cmake
@pytest.mark.parametrize(
    "host",
    [
        "native",
        pytest.param(
            "cross_build_iOS", marks=pytest.mark.skipif(
                platform.system() != "Darwin", reason="OSX only",
            ),
        ),
    ],
)
def test_cmaketoolchain_path_find_package_real_config(host):
    client = TestClient()

    cross_build = "cross_build" in host
    if cross_build:
        host_profile = "ios12.0-armv8"
        profile_content = textwrap.dedent("""
            include(default)
            [settings]
            os=iOS
            os.version=12.0
            arch=armv8
        """)
        client.save({host_profile: profile_content})

    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.cmake import CMake
        import os
        class TestConan(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            exports = "*"
            generators = "CMakeToolchain"

            def layout(self):
                pass

            def build(self):
                cmake = CMake(self)
                cmake.configure()

            def package(self):
                cmake = CMake(self)
                cmake.install()

            def package_info(self):
                self.cpp_info.builddirs.append(os.path.join("hello", "cmake"))
        """)
    cmake = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(MyHello NONE)

        add_library(hello INTERFACE)
        install(TARGETS hello EXPORT helloConfig)
        export(TARGETS hello
            NAMESPACE hello::
            FILE "${CMAKE_CURRENT_BINARY_DIR}/helloConfig.cmake"
        )
        install(EXPORT helloConfig
            DESTINATION "${CMAKE_INSTALL_PREFIX}/hello/cmake"
            NAMESPACE hello::
        )
        """)
    client.save({"conanfile.py": conanfile, "CMakeLists.txt": cmake})
    client.run("create . hello/0.1@{}".format(
        " -pr:b default -pr:h {}".format(host_profile) if cross_build else "",
    ))

    consumer = textwrap.dedent("""
        project(MyHello NONE)
        cmake_minimum_required(VERSION 3.15)

        find_package(hello REQUIRED)
        """)

    client.save({"CMakeLists.txt": consumer}, clean_first=True)
    if cross_build:
        client.save({host_profile: profile_content})
    client.run("install hello/0.1@ -g CMakeToolchain{}".format(
        " -pr:b default -pr:h {}".format(host_profile) if cross_build else "",
    ))
    with client.chdir("build"):
        client.run_command("cmake .. -DCMAKE_TOOLCHAIN_FILE=../conan_toolchain.cmake")
    # If it didn't fail, it found the helloConfig.cmake
    assert "Conan: Target declared" not in client.out

    # If using the CMakeDeps generator, the in-package .cmake will be ignored
    client.run("install hello/0.1@ -g CMakeToolchain -g CMakeDeps{}".format(
        " -pr:b default -pr:h {}".format(host_profile) if cross_build else "",
    ))
    with client.chdir("build2"):  # A clean folder, not the previous one, CMake cache doesnt affect
        client.run_command("cmake .. -DCMAKE_TOOLCHAIN_FILE=../conan_toolchain.cmake")
    assert "Conan: Target declared 'hello::hello'" in client.out


@pytest.mark.tool_cmake
@pytest.mark.parametrize("require_type", ["requires", "build_requires"])
def test_cmaketoolchain_path_include_cmake_modules(require_type):
    """Test that cmake module files in builddirs of requires and build_requires
    are accessible with include() in consumer CMakeLists
    """
    client = TestClient()

    conanfile = textwrap.dedent("""
        from conans import ConanFile
        class TestConan(ConanFile):
            settings = "os", "compiler", "arch", "build_type"
            exports = "*"
            def layout(self):
                pass
            def package(self):
                self.copy(pattern="*")
            def package_info(self):
                self.cpp_info.builddirs.append("cmake")
    """)
    myowncmake = 'MESSAGE("MYOWNCMAKE FROM hello!")'
    client.save({"conanfile.py": conanfile, "cmake/myowncmake.cmake": myowncmake})
    client.run("create . hello/0.1@")

    conanfile = textwrap.dedent("""
        from conans import ConanFile
        class PkgConan(ConanFile):
            settings = "os", "compiler", "arch", "build_type"
            {require_type} = "hello/0.1"
    """.format(require_type=require_type))
    consumer = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(MyHello)
        include(myowncmake)
    """)
    client.save({"conanfile.py": conanfile, "CMakeLists.txt": consumer}, clean_first=True)
    client.run("install . pkg/0.1@ -g CMakeToolchain")
    with client.chdir("build"):
        client.run_command("cmake .. -DCMAKE_TOOLCHAIN_FILE=../conan_toolchain.cmake")
    assert "MYOWNCMAKE FROM hello!" in client.out


@pytest.mark.tool_cmake
@pytest.mark.parametrize(
    "host",
    [
        "native",
        pytest.param(
            "cross_build_iOS", marks=pytest.mark.skipif(
                platform.system() != "Darwin", reason="OSX only",
            ),
        ),
    ],
)
def test_cmaketoolchain_path_find_file_find_path(host):
    """Test that headers in includedirs of requires can be found with
    find_file() and find_path() in consumer CMakeLists
    """
    client = TestClient()

    cross_build = "cross_build" in host
    if cross_build:
        host_profile = "ios12.0-armv8"
        profile_content = textwrap.dedent("""
            include(default)
            [settings]
            os=iOS
            os.version=12.0
            arch=armv8
        """)
        client.save({host_profile: profile_content})

    conanfile = textwrap.dedent("""
        from conans import ConanFile
        class TestConan(ConanFile):
            settings = "os", "arch", "compiler", "build_type"
            exports = "*"
            def layout(self):
                pass
            def package(self):
                self.copy(pattern="*.h", dst="include")
    """)
    client.save({"conanfile.py": conanfile, "hello.h": ""})
    client.run("create . hello/0.1@{}".format(
        " -pr:b default -pr:h {}".format(host_profile) if cross_build else "",
    ))

    consumer = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(MyHello)
        find_file(HELLOFILE hello.h)
        if(HELLOFILE)
            message("Found file hello.h")
        endif()
        find_path(HELLODIR hello.h)
        if(HELLODIR)
            message("Found path of hello.h")
        endif()
    """)
    client.save({"CMakeLists.txt": consumer}, clean_first=True)
    if cross_build:
        client.save({host_profile: profile_content})
    client.run("install hello/0.1@ -g CMakeToolchain{}".format(
        " -pr:b default -pr:h {}".format(host_profile) if cross_build else "",
    ))
    with client.chdir("build"):
        client.run_command("cmake .. -DCMAKE_TOOLCHAIN_FILE=../conan_toolchain.cmake")
    assert "Found file hello.h" in client.out
    assert "Found path of hello.h" in client.out


@pytest.mark.tool_cmake
@pytest.mark.parametrize(
    "host",
    [
        "native",
        pytest.param(
            "cross_build_iOS", marks=pytest.mark.skipif(
                platform.system() != "Darwin", reason="OSX only",
            ),
        ),
    ],
)
def test_cmaketoolchain_path_find_library(host):
    """Test that libraries in libdirs of requires can be found with
    find_library() in consumer CMakeLists
    """
    client = TestClient()

    cross_build = "cross_build" in host
    if cross_build:
        host_profile = "ios12.0-armv8"
        profile_content = textwrap.dedent("""
            include(default)
            [settings]
            os=iOS
            os.version=12.0
            arch=armv8
        """)
        client.save({host_profile: profile_content})

    conanfile = textwrap.dedent("""
        from conans import ConanFile
        class TestConan(ConanFile):
            settings = "os", "arch", "compiler", "build_type"
            exports = "*"
            def layout(self):
                pass
            def package(self):
                self.copy(pattern="*", dst="lib")
    """)
    client.save({"conanfile.py": conanfile, "libhello.a": "", "hello.lib": ""})
    client.run("create . hello_host/0.1@{}".format(
        " -pr:b default -pr:h {}".format(host_profile) if cross_build else "",
    ))
    client.run("create . hello_build/0.1@")

    conanfile = textwrap.dedent("""
        from conans import ConanFile
        class PkgConan(ConanFile):
            settings = "os", "arch", "compiler", "build_type"
            requires = "hello_host/0.1"
            build_requires = "hello_build/0.1"
    """)
    consumer = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(MyHello)
        find_library(HELLOLIB hello)
        if(HELLOLIB)
            message("Found hello lib: ${HELLOLIB}")
        endif()
    """)
    client.save({"conanfile.py": conanfile, "CMakeLists.txt": consumer}, clean_first=True)
    if cross_build:
        client.save({host_profile: profile_content})
    client.run("install . pkg/0.1@ -g CMakeToolchain{}".format(
        " -pr:b default -pr:h {}".format(host_profile) if cross_build else "",
    ))
    with client.chdir("build"):
        client.run_command("cmake .. -DCMAKE_TOOLCHAIN_FILE=../conan_toolchain.cmake")
    assert "Found hello lib" in client.out
    assert "hello_host/0.1/" in client.out
    assert "hello_build/0.1/" not in client.out


@pytest.mark.tool_cmake
@pytest.mark.parametrize(
    "host",
    [
        "native",
        pytest.param(
            "cross_build_iOS", marks=pytest.mark.skipif(
                platform.system() != "Darwin", reason="OSX only",
            ),
        ),
    ],
)
def test_cmaketoolchain_path_find_program(host):
    """Test that executables in bindirs of build_requires can be found with
    find_program() in consumer CMakeLists.
    """
    client = TestClient()

    cross_build = "cross_build" in host
    if cross_build:
        host_profile = "ios12.0-armv8"
        profile_content = textwrap.dedent("""
            include(default)
            [settings]
            os=iOS
            os.version=12.0
            arch=armv8
        """)
        client.save({host_profile: profile_content})

    conanfile = textwrap.dedent("""
        from conans import ConanFile
        class TestConan(ConanFile):
            settings = "os", "arch", "compiler", "build_type"
            exports = "*"
            def layout(self):
                pass
            def package(self):
                self.copy(pattern="*", dst="bin")
    """)
    client.save({"conanfile.py": conanfile, "hello": "", "hello.exe": ""})
    client.run("create . hello_host/0.1@{}".format(
        " -pr:b default -pr:h {}".format(host_profile) if cross_build else "",
    ))
    client.run("create . hello_build/0.1@")

    conanfile = textwrap.dedent("""
        from conans import ConanFile
        class PkgConan(ConanFile):
            settings = "os", "arch", "compiler", "build_type"
            requires = "hello_host/0.1"
            build_requires = "hello_build/0.1"
    """)
    consumer = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(MyHello)
        find_program(HELLOPROG hello)
        if(HELLOPROG)
            message("Found hello prog: ${HELLOPROG}")
        endif()
    """)
    client.save({"conanfile.py": conanfile, "CMakeLists.txt": consumer}, clean_first=True)
    if cross_build:
        client.save({host_profile: profile_content})
    client.run("install . pkg/0.1@ -g CMakeToolchain{}".format(
        " -pr:b default -pr:h {}".format(host_profile) if cross_build else "",
    ))
    with client.chdir("build"):
        client.run_command("cmake .. -DCMAKE_TOOLCHAIN_FILE=../conan_toolchain.cmake")
    assert "Found hello prog" in client.out
    assert "hello_host/0.1/" not in client.out
    assert "hello_build/0.1/" in client.out
