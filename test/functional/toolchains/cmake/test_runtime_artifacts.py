import json
import textwrap

import pytest

from conan.test.utils.tools import TestClient


liba_cmake = textwrap.dedent("""\
    cmake_minimum_required(VERSION 3.15)
    project(liba CXX)

    set(CMAKE_WINDOWS_EXPORT_ALL_SYMBOLS ON)

    # This package is a static-library, but it also ships a shared library that consumers
    # have to link, and that has to be available at runtime
    add_library(myshared SHARED src/myshared.cpp)
    target_include_directories(myshared PUBLIC include)

    add_library(mystatic STATIC src/mystatic.cpp)
    target_include_directories(mystatic PUBLIC include)
    target_link_libraries(mystatic PRIVATE myshared)

    install(TARGETS mystatic myshared)
    install(DIRECTORY include/ DESTINATION include)
    """)

liba_h = textwrap.dedent("""\
    #pragma once
    void myshared_func();
    void mystatic_func();
    """)

liba_shared_cpp = textwrap.dedent("""\
    #include <iostream>
    #include "liba.h"
    void myshared_func() { std::cout << "liba: myshared_func!" << std::endl; }
    """)

liba_static_cpp = textwrap.dedent("""\
    #include <iostream>
    #include "liba.h"
    void mystatic_func() {
        std::cout << "liba: mystatic_func!" << std::endl;
        myshared_func();
    }
    """)


def _liba_conanfile(runtime_artifacts):
    return textwrap.dedent(f"""\
        from conan import ConanFile
        from conan.tools.cmake import CMake, cmake_layout

        class LibA(ConanFile):
            name = "liba"
            version = "0.1"
            package_type = "static-library"
            runtime_artifacts = {runtime_artifacts}
            settings = "os", "compiler", "build_type", "arch"
            generators = "CMakeToolchain"
            exports_sources = "CMakeLists.txt", "include/*", "src/*"

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
                # "mystatic" first, it is the one requiring symbols from "myshared"
                self.cpp_info.libs = ["mystatic", "myshared"]
        """)


def _liba_files(runtime_artifacts):
    return {"liba/conanfile.py": _liba_conanfile(runtime_artifacts),
            "liba/CMakeLists.txt": liba_cmake,
            "liba/include/liba.h": liba_h,
            "liba/src/myshared.cpp": liba_shared_cpp,
            "liba/src/mystatic.cpp": liba_static_cpp}


app_conanfile = textwrap.dedent("""\
    import os
    from conan import ConanFile
    from conan.tools.cmake import CMake, cmake_layout

    class App(ConanFile):
        settings = "os", "compiler", "build_type", "arch"
        package_type = "application"
        generators = "CMakeToolchain", "CMakeDeps"
        requires = "{requires}"

        def layout(self):
            cmake_layout(self)

        def build(self):
            cmake = CMake(self)
            cmake.configure()
            cmake.build()
            self.run(os.path.join(self.cpp.build.bindir, "app"), env="conanrun")
    """)


@pytest.mark.tool("cmake")
def test_static_lib_shipping_shared_lib():
    """ a package_type=static-library package that also contains a shared library, which the
    consumer links too, and which has to be available at runtime => runtime_artifacts=True
    """
    c = TestClient()
    app_cmake = textwrap.dedent("""\
        cmake_minimum_required(VERSION 3.15)
        project(app CXX)

        find_package(liba CONFIG REQUIRED)

        add_executable(app main.cpp)
        target_link_libraries(app PRIVATE liba::liba)
        """)
    main_cpp = textwrap.dedent("""\
        #include "liba.h"
        int main() {
            mystatic_func();
        }
        """)
    c.save(_liba_files(runtime_artifacts=True))
    c.save({"app/conanfile.py": app_conanfile.format(requires="liba/0.1"),
            "app/CMakeLists.txt": app_cmake,
            "app/main.cpp": main_cpp})
    c.run("create liba")

    c.run("graph info app --format=json", redirect_stdout="graph.json")
    liba_require = json.loads(c.load("graph.json"))["graph"]["nodes"]["0"]["dependencies"]["1"]
    # The "run" trait is True, even if liba is a static-library
    assert liba_require["ref"] == "liba/0.1"
    assert liba_require["run"] is True
    assert liba_require["libs"] is True

    c.run("build app")
    # If "runtime_artifacts" was not defined, run=False, so the shared library location would
    # not be in the "conanrun" environment, and this would fail to run in Windows
    assert "liba: mystatic_func!" in c.out
    assert "liba: myshared_func!" in c.out


@pytest.mark.tool("cmake")
@pytest.mark.parametrize("runtime_artifacts", [True, False])
def test_static_lib_shipping_shared_lib_transitive(runtime_artifacts):
    """ app -> libb (shared-library) -> liba (static-library shipping a shared library)
    The libs of liba are linked into libb.so, so app doesn't need them, but the shared library
    inside liba still has to be there at runtime, so its binary cannot be skipped
    """
    c = TestClient()
    libb_conanfile = textwrap.dedent("""\
        from conan import ConanFile
        from conan.tools.cmake import CMake, cmake_layout

        class LibB(ConanFile):
            name = "libb"
            version = "0.1"
            package_type = "shared-library"
            settings = "os", "compiler", "build_type", "arch"
            generators = "CMakeToolchain", "CMakeDeps"
            requires = "liba/0.1"
            exports_sources = "CMakeLists.txt", "include/*", "src/*"

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
                self.cpp_info.libs = ["libb"]
        """)
    libb_cmake = textwrap.dedent("""\
        cmake_minimum_required(VERSION 3.15)
        project(libb CXX)

        set(CMAKE_WINDOWS_EXPORT_ALL_SYMBOLS ON)
        find_package(liba CONFIG REQUIRED)

        add_library(libb SHARED src/libb.cpp)
        target_include_directories(libb PUBLIC include)
        target_link_libraries(libb PRIVATE liba::liba)

        install(TARGETS libb)
        install(DIRECTORY include/ DESTINATION include)
        """)
    app_cmake = textwrap.dedent("""\
        cmake_minimum_required(VERSION 3.15)
        project(app CXX)

        find_package(libb CONFIG REQUIRED)

        add_executable(app main.cpp)
        target_link_libraries(app PRIVATE libb::libb)
        """)
    c.save(_liba_files(runtime_artifacts))
    c.save({"libb/conanfile.py": libb_conanfile,
            "libb/CMakeLists.txt": libb_cmake,
            "libb/include/libb.h": "#pragma once\nvoid libb_func();\n",
            "libb/src/libb.cpp": '#include "libb.h"\n#include "liba.h"\n'
                                 "void libb_func() { mystatic_func(); }\n",
            "app/conanfile.py": app_conanfile.format(requires="libb/0.1"),
            "app/CMakeLists.txt": app_cmake,
            "app/main.cpp": '#include "libb.h"\nint main() { libb_func(); }\n'})
    c.run("create liba")
    c.run("create libb")

    if runtime_artifacts:
        c.run("build app")
        # The liba binary is necessary at runtime, so it cannot be skipped
        assert "Skipped binaries" not in c.out
        assert "liba: mystatic_func!" in c.out
        assert "liba: myshared_func!" in c.out
    else:
        # Without "runtime_artifacts" the run trait is False, and as liba is a static-library
        # linked inside libb, Conan understands its binary is not necessary anymore and skips it,
        # but the shared library it ships is still necessary, and the app cannot run
        c.run("build app", assert_error=True)
        assert "Skipped binaries" in c.out
        assert "liba/0.1" in c.out
        assert "Error in build() method" in c.out
