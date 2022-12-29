import platform
import textwrap

import pytest

from conans.test.utils.tools import TestClient


ios10_armv8_settings = "-s os=iOS -s os.sdk=iphoneos -s os.version=10.0 -s arch=armv8"


class _FindRootPathModes(object):
    def __init__(self, package=None, library=None, framework=None, include=None, program=None):
        self.package = package
        self.library = library
        self.framework = framework
        self.include = include
        self.program = program


find_root_path_modes_default = _FindRootPathModes()
find_root_path_modes_cross_build = _FindRootPathModes(
    package="ONLY",
    library="ONLY",
    framework="ONLY",
    include="ONLY",
    program="NEVER",
)


def _cmake_command_toolchain(find_root_path_modes):
    build_type = "-DCMAKE_BUILD_TYPE=Release" if platform.system() != "Windows" else ""
    cmake_command = "cmake .. -DCMAKE_TOOLCHAIN_FILE=../conan_toolchain.cmake {}".format(build_type)
    if find_root_path_modes.package:
        cmake_command += " -DCMAKE_FIND_ROOT_PATH_MODE_PACKAGE={}".format(find_root_path_modes.package)
    if find_root_path_modes.library:
        cmake_command += " -DCMAKE_FIND_ROOT_PATH_MODE_LIBRARY={}".format(find_root_path_modes.library)
    if find_root_path_modes.framework:
        cmake_command += " -DCMAKE_FIND_ROOT_PATH_MODE_FRAMEWORK={}".format(find_root_path_modes.framework)
    if find_root_path_modes.include:
        cmake_command += " -DCMAKE_FIND_ROOT_PATH_MODE_INCLUDE={}".format(find_root_path_modes.include)
    if find_root_path_modes.program:
        cmake_command += " -DCMAKE_FIND_ROOT_PATH_MODE_PROGRAM={}".format(find_root_path_modes.program)
    return cmake_command


@pytest.mark.tool_cmake
@pytest.mark.parametrize("package", ["hello", "ZLIB"])
@pytest.mark.parametrize("find_package", ["module", "config"])
@pytest.mark.parametrize(
    "settings",
    [
        "",
        pytest.param(
            ios10_armv8_settings,
            marks=pytest.mark.skipif(platform.system() != "Darwin", reason="OSX only"),
        ),
    ],
)
@pytest.mark.parametrize(
    "find_root_path_modes", [find_root_path_modes_default, find_root_path_modes_cross_build],
)
def test_cmaketoolchain_path_find_package(package, find_package, settings, find_root_path_modes):
    """Test with user "Hello" and also ZLIB one, to check that package ZLIB
    has priority over the CMake system one
    """
    client = TestClient()

    conanfile = textwrap.dedent("""
        from conans import ConanFile
        class TestConan(ConanFile):
            exports_sources = "*"
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
    client.run("create . {}/0.1@ -pr:b default {}".format(package, settings))

    consumer = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(MyHello CXX)
        find_package({package} REQUIRED)
        """).format(package=package)

    client.save({"CMakeLists.txt": consumer}, clean_first=True)
    client.run("install {}/0.1@ -g CMakeToolchain -pr:b default {}".format(package, settings))
    with client.chdir("build"):
        client.run_command(_cmake_command_toolchain(find_root_path_modes))
    assert "Conan: Target declared" not in client.out
    assert "HELLO FROM THE {package} FIND PACKAGE!".format(package=package) in client.out

    # If using the CMakeDeps generator, the in-package .cmake will be ignored
    client.run("install {}/0.1@ -g CMakeToolchain -g CMakeDeps -pr:b default {}".format(
        package, settings,
    ))
    with client.chdir("build2"):  # A clean folder, not the previous one, CMake cache doesnt affect
        client.run_command(_cmake_command_toolchain(find_root_path_modes))
    assert "Conan: Target declared '{package}::{package}'".format(package=package) in client.out
    assert "HELLO FROM THE {package} FIND PACKAGE!".format(package=package) not in client.out


def test_cmaketoolchain_path_find_package_editable():
    """ make sure a package in editable mode that contains a xxxConfig.cmake file can find that
    file in the user folder
    """
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import cmake_layout
        class TestConan(ConanFile):
            settings = "os", "compiler", "arch", "build_type"
            exports_sources = "*"
            def layout(self):
                cmake_layout(self)
                self.cpp.source.builddirs = ["cmake"]
            def package(self):
                self.copy(pattern="*")
            def package_info(self):
                self.cpp_info.builddirs.append("cmake")
        """)
    find = textwrap.dedent("""
        SET(hello_FOUND 1)
        MESSAGE("HELLO FROM THE hello FIND PACKAGE!")
        """)

    consumer = textwrap.dedent("""\
        cmake_minimum_required(VERSION 3.15)
        project(MyHello CXX)
        find_package(hello REQUIRED)
        """)
    client.save({"dep/conanfile.py": conanfile,
                 "dep/cmake/helloConfig.cmake": find,
                 "consumer/conanfile.txt": "[requires]\nhello/0.1\n[generators]\nCMakeToolchain",
                 "consumer/CMakeLists.txt": consumer})
    with client.chdir("dep"):
        client.run("install .")
        client.run("editable add . hello/0.1@")

    with client.chdir("consumer"):
        client.run("install .")

        with client.chdir("build"):
            build_type = "-DCMAKE_BUILD_TYPE=Release" if platform.system() != "Windows" else ""
            cmake_command = "cmake .. -DCMAKE_TOOLCHAIN_FILE=../conan_toolchain.cmake {}".format(
                build_type)
            client.run_command(cmake_command)
        assert "Conan: Target declared" not in client.out
        assert "HELLO FROM THE hello FIND PACKAGE!" in client.out


@pytest.mark.tool_cmake
@pytest.mark.parametrize(
    "settings",
    [
        "",
        pytest.param(
            ios10_armv8_settings,
            marks=pytest.mark.skipif(platform.system() != "Darwin", reason="OSX only"),
        ),
    ],
)
@pytest.mark.parametrize(
    "find_root_path_modes", [find_root_path_modes_default, find_root_path_modes_cross_build],
)
def test_cmaketoolchain_path_find_package_real_config(settings, find_root_path_modes):
    client = TestClient()

    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.cmake import CMake
        import os
        class TestConan(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            exports_sources = "*"
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
    client.run("create . hello/0.1@ -pr:b default {}".format(settings))

    consumer = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(MyHello NONE)

        find_package(hello REQUIRED)
        """)

    client.save({"CMakeLists.txt": consumer}, clean_first=True)
    client.run("install hello/0.1@ -g CMakeToolchain -pr:b default {}".format(settings))
    with client.chdir("build"):
        client.run_command(_cmake_command_toolchain(find_root_path_modes))
    # If it didn't fail, it found the helloConfig.cmake
    assert "Conan: Target declared" not in client.out

    # If using the CMakeDeps generator, the in-package .cmake will be ignored
    client.run("install hello/0.1@ -g CMakeToolchain -g CMakeDeps -pr:b default {}".format(settings))
    with client.chdir("build2"):  # A clean folder, not the previous one, CMake cache doesnt affect
        client.run_command(_cmake_command_toolchain(find_root_path_modes))
    assert "Conan: Target declared 'hello::hello'" in client.out


@pytest.mark.tool_cmake
@pytest.mark.parametrize("require_type", ["requires", "build_requires"])
@pytest.mark.parametrize(
    "settings",
    [
        "",
        pytest.param(
            ios10_armv8_settings,
            marks=pytest.mark.skipif(platform.system() != "Darwin", reason="OSX only"),
        ),
    ],
)
@pytest.mark.parametrize(
    "find_root_path_modes", [find_root_path_modes_default, find_root_path_modes_cross_build],
)
def test_cmaketoolchain_path_include_cmake_modules(require_type, settings, find_root_path_modes):
    """Test that cmake module files in builddirs of requires and build_requires
    are accessible with include() in consumer CMakeLists
    """
    client = TestClient()

    conanfile = textwrap.dedent("""
        from conans import ConanFile
        class TestConan(ConanFile):
            settings = "os", "compiler", "arch", "build_type"
            exports_sources = "*"
            def layout(self):
                pass
            def package(self):
                self.copy(pattern="*")
            def package_info(self):
                self.cpp_info.builddirs.append("cmake")
    """)
    myowncmake = 'MESSAGE("MYOWNCMAKE FROM hello!")'
    client.save({"conanfile.py": conanfile, "cmake/myowncmake.cmake": myowncmake})
    client.run("create . hello/0.1@{}".format(
        " -pr:b default {}".format(settings) if require_type == "requires" else "",
    ))

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
    client.run("install . pkg/0.1@ -g CMakeToolchain -pr:b default {}".format(settings))
    with client.chdir("build"):
        client.run_command(_cmake_command_toolchain(find_root_path_modes))
    assert "MYOWNCMAKE FROM hello!" in client.out


@pytest.mark.tool_cmake
@pytest.mark.parametrize(
    "settings",
    [
        "",
        pytest.param(
            ios10_armv8_settings,
            marks=pytest.mark.skipif(platform.system() != "Darwin", reason="OSX only"),
        ),
    ],
)
@pytest.mark.parametrize(
    "find_root_path_modes", [find_root_path_modes_default, find_root_path_modes_cross_build],
)
def test_cmaketoolchain_path_find_file_find_path(settings, find_root_path_modes):
    """Test that headers in includedirs of requires can be found with
    find_file() and find_path() in consumer CMakeLists
    """
    client = TestClient()

    conanfile = textwrap.dedent("""
        from conans import ConanFile
        class TestConan(ConanFile):
            settings = "os", "arch", "compiler", "build_type"
            exports_sources = "*"
            def layout(self):
                pass
            def package(self):
                self.copy(pattern="*.h", dst="include")
    """)
    client.save({"conanfile.py": conanfile, "hello.h": ""})
    client.run("create . hello/0.1@ -pr:b default {}".format(settings))

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
    client.run("install hello/0.1@ -g CMakeToolchain -pr:b default {}".format(settings))
    with client.chdir("build"):
        client.run_command(_cmake_command_toolchain(find_root_path_modes))
    assert "Found file hello.h" in client.out
    assert "Found path of hello.h" in client.out


@pytest.mark.tool_cmake
@pytest.mark.parametrize(
    "settings",
    [
        "",
        pytest.param(
            ios10_armv8_settings,
            marks=pytest.mark.skipif(platform.system() != "Darwin", reason="OSX only"),
        ),
    ],
)
@pytest.mark.parametrize(
    "find_root_path_modes", [find_root_path_modes_default, find_root_path_modes_cross_build],
)
def test_cmaketoolchain_path_find_library(settings, find_root_path_modes):
    """Test that libraries in libdirs of requires can be found with
    find_library() in consumer CMakeLists
    """
    client = TestClient()

    conanfile = textwrap.dedent("""
        from conans import ConanFile
        class TestConan(ConanFile):
            settings = "os", "arch", "compiler", "build_type"
            exports_sources = "*"
            def layout(self):
                pass
            def package(self):
                self.copy(pattern="*", dst="lib")
    """)
    client.save({"conanfile.py": conanfile, "libhello.a": "", "hello.lib": ""})
    client.run("create . hello_host/0.1@ -pr:b default {}".format(settings))
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
    client.run("install . pkg/0.1@ -g CMakeToolchain -pr:b default {}".format(settings))
    with client.chdir("build"):
        client.run_command(_cmake_command_toolchain(find_root_path_modes))
    assert "Found hello lib" in client.out
    assert "hello_host/0.1/" in client.out
    assert "hello_build/0.1/" not in client.out


@pytest.mark.tool_cmake
@pytest.mark.parametrize(
    "settings",
    [
        "",
        pytest.param(
            ios10_armv8_settings,
            marks=pytest.mark.skipif(platform.system() != "Darwin", reason="OSX only"),
        ),
    ],
)
@pytest.mark.parametrize(
    "find_root_path_modes", [find_root_path_modes_default, find_root_path_modes_cross_build],
)
def test_cmaketoolchain_path_find_program(settings, find_root_path_modes):
    """Test that executables in bindirs of build_requires can be found with
    find_program() in consumer CMakeLists.
    """
    client = TestClient()

    conanfile = textwrap.dedent("""
        from conans import ConanFile
        class TestConan(ConanFile):
            settings = "os", "arch", "compiler", "build_type"
            exports_sources = "*"
            def layout(self):
                pass
            def package(self):
                self.copy(pattern="*", dst="bin")
    """)
    client.save({"conanfile.py": conanfile, "hello": "", "hello.exe": ""})
    client.run("create . hello_host/0.1@ -pr:b default {}".format(settings))
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
    client.run("install . pkg/0.1@ -g CMakeToolchain -pr:b default {}".format(settings))
    with client.chdir("build"):
        client.run_command(_cmake_command_toolchain(find_root_path_modes))
    assert "Found hello prog" in client.out
    assert "hello_host/0.1/" not in client.out
    assert "hello_build/0.1/" in client.out
