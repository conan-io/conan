import os
import platform
import textwrap

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.assets.pkg_cmake import pkg_cmake_app
from conan.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() != "Windows", reason="Only windows")
def test_editable_msbuild():
    c = TestClient()
    with c.chdir("dep"):
        c.run("new msbuild_lib -d name=dep -d version=0.1")
    c.save(pkg_cmake_app("pkg", "0.1", requires=["dep/0.1"]),
           path=os.path.join(c.current_folder, "pkg"))

    build_folder = ""
    output_folder = '--output-folder="{}"'.format(build_folder) if build_folder else ""
    build_folder = '--build-folder="{}"'.format(build_folder) if build_folder else ""

    def build_dep():
        c.run("install . {}".format(output_folder))
        c.run("build . {}".format(build_folder))
        c.run("install . -s build_type=Debug {}".format(output_folder))
        c.run("build . -s build_type=Debug {}".format(build_folder))

    with c.chdir("dep"):
        c.run("editable add . {}".format(output_folder))
        build_dep()

    def build_pkg(msg):
        c.run("build . ")
        folder = os.path.join("build", "Release")
        c.run_command(os.sep.join([".", folder, "pkg"]))
        assert "main: Release!" in c.out
        assert "{}: Hello World Release!".format(msg) in c.out
        c.run("build . -s build_type=Debug")
        folder = os.path.join("build", "Debug")
        c.run_command(os.sep.join([".", folder, "pkg"]))
        assert "main: Debug!" in c.out
        assert "{}: Hello World Debug!".format(msg) in c.out

    with c.chdir("pkg"):
        c.run("install . ")
        c.run("install . -s build_type=Debug")
        build_pkg("dep/0.1")

    # Do a source change in the editable!
    with c.chdir("dep"):
        dep_cpp = c.load("src/dep.cpp")
        dep_cpp = dep_cpp.replace("dep/", "SUPERDEP/")
        c.save({"src/dep.cpp": dep_cpp})
        build_dep()

    with c.chdir("pkg"):
        build_pkg("SUPERDEP/0.1")

    # Check that create is still possible
    c.run("editable remove dep")
    c.run("create dep")
    c.run("create pkg")
    # print(c.out)
    assert "pkg/0.1: Created package" in c.out


@pytest.mark.skipif(platform.system() != "Windows", reason="Only for windows")
def test_editable_msbuilddeps():
    # https://github.com/conan-io/conan/issues/12521
    c = TestClient()
    dep = textwrap.dedent("""
        from conan import ConanFile
        class Dep(ConanFile):
            name = "dep"
            version = "0.1"
            def layout(self):
                pass
            """)
    c.save({"dep/conanfile.py": dep,
            "pkg/conanfile.py": GenConanfile("pkg", "0.1").with_settings("build_type", "arch")
                                                          .with_requires("dep/0.1")
                                                          .with_generator("MSBuildDeps")})
    c.run("editable add dep")
    c.run("install pkg")
    # It doesn't crash anymore
    assert "dep/0.1:da39a3ee5e6b4b0d3255bfef95601890afd80709 - Editable" in c.out
