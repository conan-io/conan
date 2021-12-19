import os
import textwrap

import pytest

from conans.test.utils.tools import TestClient


@pytest.mark.tool_cmake
@pytest.mark.parametrize("package", ["hello", "ZLIB"])
@pytest.mark.parametrize("find_package", ["module", "config"])
def test_cmaketoolchain_path_find_package(package, find_package):
    """Test with user "Hello" and also ZLIB one, to check that package ZLIB
    has priority over the CMake system one
    """
    client = TestClient()
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
    client.save({"conanfile.py": conanfile})
    client.save({"{}".format(filename): find},
                os.path.join(client.current_folder, "cmake"))
    client.run("create . {}/0.1@".format(package))

    consumer = textwrap.dedent("""
        set(CMAKE_CXX_COMPILER_WORKS 1)
        set(CMAKE_CXX_ABI_COMPILED 1)
        cmake_minimum_required(VERSION 3.15)
        project(MyHello CXX)
        find_package({package} REQUIRED)
        """).format(package=package)

    client.save({"CMakeLists.txt": consumer}, clean_first=True)
    client.run("install {}/0.1@ -g CMakeToolchain".format(package))
    with client.chdir("build"):
        client.run_command("cmake .. -DCMAKE_TOOLCHAIN_FILE=../conan_toolchain.cmake")
    assert "Conan: Target declared" not in client.out
    assert "HELLO FROM THE {package} FIND PACKAGE!".format(package=package) in client.out

    # If using the CMakeDeps generator, the in-package .cmake will be ignored
    client.run("install {}/0.1@ -g CMakeToolchain -g CMakeDeps".format(package))
    with client.chdir("build2"):  # A clean folder, not the previous one, CMake cache doesnt affect
        client.run_command("cmake .. -DCMAKE_TOOLCHAIN_FILE=../conan_toolchain.cmake")
    assert "Conan: Target declared '{package}::{package}'".format(package=package) in client.out
    assert "HELLO FROM THE {package} FIND PACKAGE!".format(package=package) not in client.out


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
    myowncmake = textwrap.dedent("""
        MESSAGE("MYOWNCMAKE FROM hello!")
    """)
    client.save({"conanfile.py": conanfile})
    client.save({"myowncmake.cmake": myowncmake},
                os.path.join(client.current_folder, "cmake"))
    client.run("create . hello/0.1@")

    conanfile = textwrap.dedent("""
        from conans import ConanFile
        class Pkg(ConanFile):
            settings = "os", "compiler", "arch", "build_type"
            {require_type} = "hello/0.1"
    """.format(require_type=require_type))
    consumer = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(MyHello)
        include(myowncmake)
    """)
    client.save({"conanfile.py": conanfile,
                 "CMakeLists.txt": consumer}, clean_first=True)
    client.run("install . pkg/0.1@ -g CMakeToolchain")
    with client.chdir("build"):
        client.run_command("cmake .. -DCMAKE_TOOLCHAIN_FILE=../conan_toolchain.cmake")
    assert "MYOWNCMAKE FROM hello!" in client.out


@pytest.mark.tool_cmake
def test_cmaketoolchain_path_find_file_find_path():
    """Test that headers in includedirs of requires can be found with
    find_file() and find_path() in consumer CMakeLists
    """
    client = TestClient()

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
    client.run("create . hello/0.1@")

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
    client.run("install hello/0.1@ -g CMakeToolchain")
    with client.chdir("build"):
        client.run_command("cmake .. -DCMAKE_TOOLCHAIN_FILE=../conan_toolchain.cmake")
    assert "Found file hello.h" in client.out
    assert "Found path of hello.h" in client.out


@pytest.mark.tool_cmake
def test_cmaketoolchain_path_find_library():
    """Test that libraries in libdirs of requires can be found with
    find_library() in consumer CMakeLists
    """
    client = TestClient()

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
    client.run("create . hello/0.1@")

    consumer = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(MyHello)
        find_library(HELLOLIB hello)
        if(HELLOLIB)
            message("Found hello lib")
        endif()
    """)
    client.save({"CMakeLists.txt": consumer}, clean_first=True)
    client.run("install hello/0.1@ -g CMakeToolchain")
    with client.chdir("build"):
        client.run_command("cmake .. -DCMAKE_TOOLCHAIN_FILE=../conan_toolchain.cmake")
    assert "Found hello lib" in client.out


@pytest.mark.tool_cmake
def test_cmaketoolchain_path_find_program():
    """Test that executables in bindirs of build_requires can be found with
    find_program() in consumer CMakeLists.
    Moreover, they must be found before any other executable of requires.
    """
    client = TestClient()

    conanfile = textwrap.dedent("""
        import os
        from conans import ConanFile
        class TestConan(ConanFile):
            settings = "os", "arch", "compiler", "build_type"
            exports = "*"
            def layout(self):
                pass
            def package(self):
                self.copy(pattern="*", dst="bin")
            def package_info(self):
                self.cpp_info.bindirs = [os.path.join("bin", "require_host")]
    """)
    client.save({"conanfile.py": conanfile,
                 "require_host/hello": "", "require_host/hello.exe": ""})
    client.run("create . hello_host/0.1@")

    conanfile = textwrap.dedent("""
        import os
        from conans import ConanFile
        class TestConan(ConanFile):
            settings = "os", "arch", "compiler", "build_type"
            exports = "*"
            def layout(self):
                pass
            def package(self):
                self.copy(pattern="*", dst="bin")
            def package_info(self):
                self.cpp_info.bindirs = [os.path.join("bin", "require_build")]
    """)
    client.save({"conanfile.py": conanfile,
                 "require_build/hello": "", "require_build/hello.exe": ""},
                clean_first=True)
    client.run("create . hello_build/0.1@")

    conanfile = textwrap.dedent("""
        from conans import ConanFile
        class TestConan(ConanFile):
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
    client.save({"conanfile.py": conanfile, "CMakeLists.txt": consumer},
                clean_first=True)
    client.run("install . pkg/0.1@ -g CMakeToolchain")
    with client.chdir("build"):
        client.run_command("cmake .. -DCMAKE_TOOLCHAIN_FILE=../conan_toolchain.cmake")
    assert "Found hello prog" in client.out
    assert "require_host/hello" not in client.out
    assert "require_build/hello" in client.out


@pytest.mark.tool_cmake
def test_cmaketoolchain_path_find_real_config():
    client = TestClient()
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
    client.save({"conanfile.py": conanfile,
                 "CMakeLists.txt": cmake})
    client.run("create . hello/0.1@")

    consumer = textwrap.dedent("""
        project(MyHello NONE)
        cmake_minimum_required(VERSION 3.15)

        find_package(hello REQUIRED)
        """)

    client.save({"CMakeLists.txt": consumer}, clean_first=True)
    client.run("install hello/0.1@ -g CMakeToolchain")
    with client.chdir("build"):
        client.run_command("cmake .. -DCMAKE_TOOLCHAIN_FILE=../conan_toolchain.cmake")
    # If it didn't fail, it found the helloConfig.cmake
    assert "Conan: Target declared" not in client.out

    # If using the CMakeDeps generator, the in-package .cmake will be ignored
    # But it is still possible to include(owncmake)
    client.run("install hello/0.1@ -g CMakeToolchain -g CMakeDeps")
    with client.chdir("build2"):  # A clean folder, not the previous one, CMake cache doesnt affect
        client.run_command("cmake .. -DCMAKE_TOOLCHAIN_FILE=../conan_toolchain.cmake")
    assert "Conan: Target declared 'hello::hello'" in client.out

