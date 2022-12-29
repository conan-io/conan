import textwrap

import pytest

from conans.test.assets.cmake import gen_cmakelists
from conans.test.assets.sources import gen_function_cpp
from conans.test.utils.tools import TestClient


def test_exports_sources_own_code_in_subfolder():
    """ test that we can put the conanfile in a subfolder, and it can work. The key is
    the exports_sources() method that can do:
        os.path.join(self.recipe_folder, "..")
    And the layout: self.folders.root = ".."
    """
    c = TestClient()
    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import load, copy, save
        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"

            def layout(self):
                self.folders.root = ".."
                self.folders.source = "."
                self.folders.build = "build"
                self.folders.generators = "conangen"

            def generate(self):
                save(self, "mygen.txt", "mycontent")

            def export_sources(self):
                source_folder = os.path.join(self.recipe_folder, "..")
                copy(self, "*.txt", source_folder, self.export_sources_folder)

            def source(self):
                cmake = load(self, "CMakeLists.txt")
                self.output.info("MYCMAKE-SRC: {}".format(cmake))

            def build(self):
                path = os.path.join(self.source_folder, "CMakeLists.txt")
                cmake = load(self, path)
                self.output.info("MYCMAKE-BUILD: {}".format(cmake))
                save(self, "mylib.a", "mylib")
            """)
    c.save({"conan/conanfile.py": conanfile,
            "CMakeLists.txt": "mycmake!"})
    c.run("create conan")
    assert "pkg/0.1: MYCMAKE-SRC: mycmake!" in c.out
    assert "pkg/0.1: MYCMAKE-BUILD: mycmake!" in c.out

    # Local flow
    c.run("install conan")
    assert c.load("conangen/mygen.txt") == "mycontent"
    # SOURCE NOT CALLED! It doesnt make sense (will fail due to local exports)
    c.run("build conan")
    assert "conanfile.py (pkg/0.1): MYCMAKE-BUILD: mycmake!" in c.out
    assert c.load("build/mylib.a") == "mylib"


def test_exports_sources_common_code():
    """ very similar to the above, but intended for a multi-package project sharing some
    common code
    """
    c = TestClient()
    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import load, copy, save
        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"

            def layout(self):
                self.folders.root = ".."
                self.folders.source = "pkg"
                self.folders.build = "build"

            def export_sources(self):
                source_folder = os.path.join(self.recipe_folder, "..")
                copy(self, "*.txt", source_folder, self.export_sources_folder)
                copy(self, "*.cmake", source_folder, self.export_sources_folder)

            def source(self):
                cmake = load(self, "CMakeLists.txt")
                self.output.info("MYCMAKE-SRC: {}".format(cmake))

            def build(self):
                path = os.path.join(self.source_folder, "CMakeLists.txt")
                cmake = load(self, path)
                self.output.info("MYCMAKE-BUILD: {}".format(cmake))

                path = os.path.join(self.export_sources_folder, "common", "myutils.cmake")
                cmake = load(self, path)
                self.output.info("MYUTILS-BUILD: {}".format(cmake))
            """)
    c.save({"pkg/conanfile.py": conanfile,
            "pkg/CMakeLists.txt": "mycmake!",
            "common/myutils.cmake": "myutils!"})
    c.run("create pkg")
    assert "pkg/0.1: MYCMAKE-SRC: mycmake!" in c.out
    assert "pkg/0.1: MYCMAKE-BUILD: mycmake!" in c.out
    assert "pkg/0.1: MYUTILS-BUILD: myutils!" in c.out

    # Local flow
    c.run("install pkg")
    # SOURCE NOT CALLED! It doesnt make sense (will fail due to local exports)
    c.run("build pkg")
    assert "conanfile.py (pkg/0.1): MYCMAKE-BUILD: mycmake!" in c.out
    assert "conanfile.py (pkg/0.1): MYUTILS-BUILD: myutils!" in c.out


@pytest.mark.tool_cmake
def test_exports_sources_common_code_layout():
    """ Equal to the previous test, but actually building and using cmake_layout
    """
    c = TestClient()
    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.cmake import cmake_layout, CMake
        from conan.tools.files import load, copy, save
        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"
            settings = "os", "compiler", "build_type", "arch"
            generators = "CMakeToolchain"

            def layout(self):
                self.folders.root = ".."
                self.folders.subproject = "pkg"
                cmake_layout(self)

            def export_sources(self):
                source_folder = os.path.join(self.recipe_folder, "..")
                copy(self, "*", source_folder, self.export_sources_folder)

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()
                self.run(os.path.join(self.cpp.build.bindirs[0], "myapp"))
            """)
    cmake_include = "include(${CMAKE_CURRENT_LIST_DIR}/../common/myutils.cmake)"
    c.save({"pkg/conanfile.py": conanfile,
            "pkg/app.cpp": gen_function_cpp(name="main", includes=["../common/myheader"],
                                            preprocessor=["MYDEFINE"]),
            "pkg/CMakeLists.txt": gen_cmakelists(appsources=["app.cpp"],
                                                 custom_content=cmake_include),
            "common/myutils.cmake": 'message(STATUS "MYUTILS.CMAKE!")',
            "common/myheader.h": '#define MYDEFINE "MYDEFINEVALUE"'})
    c.run("create pkg")
    assert "MYUTILS.CMAKE!" in c.out
    assert "main: Release!" in c.out
    assert "MYDEFINE: MYDEFINEVALUE" in c.out

    # Local flow
    c.run("install pkg")
    c.run("build pkg")
    assert "MYUTILS.CMAKE!" in c.out
    assert "main: Release!" in c.out
    assert "MYDEFINE: MYDEFINEVALUE" in c.out

    c.run("install pkg -s build_type=Debug")
    c.run("build pkg")
    assert "MYUTILS.CMAKE!" in c.out
    assert "main: Debug!" in c.out
    assert "MYDEFINE: MYDEFINEVALUE" in c.out
