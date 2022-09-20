import os
import platform

import pytest

from conans.test.assets.pkg_cmake import pkg_cmake_app
from conans.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() != "Windows", reason="Only windows")
def test_editable_msbuild():
    c = TestClient()
    with c.chdir("dep"):
        c.run("new dep/0.1 -m=msbuild_lib")
    c.save(pkg_cmake_app("pkg", "0.1", requires=["dep/0.1"]),
           path=os.path.join(c.current_folder, "pkg"))

    build_folder = ""
    output_folder = '--output-folder="{}"'.format(build_folder) if build_folder else ""
    build_folder = '--build-folder="{}"'.format(build_folder) if build_folder else ""

    def build_dep():
        c.run("install . -if=install_release {}".format(output_folder))
        c.run("build . -if=install_release {}".format(build_folder))
        c.run("install . -s build_type=Debug -if=install_debug {}".format(output_folder))
        c.run("build . -if=install_debug {}".format(build_folder))

    with c.chdir("dep"):
        c.run("editable add . dep/0.1@ {}".format(output_folder))
        build_dep()

    def build_pkg(msg):
        c.run("build . -if=install_release")
        folder = os.path.join("build", "Release")
        c.run_command(os.sep.join([".", folder, "pkg"]))
        assert "main: Release!" in c.out
        assert "{}: Hello World Release!".format(msg) in c.out
        c.run("build . -if=install_debug")
        folder = os.path.join("build", "Debug")
        c.run_command(os.sep.join([".", folder, "pkg"]))
        assert "main: Debug!" in c.out
        assert "{}: Hello World Debug!".format(msg) in c.out

    with c.chdir("pkg"):
        c.run("install . -if=install_release")
        c.run("install . -if=install_debug -s build_type=Debug")
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
    c.run("editable remove dep/0.1@")
    c.run("create dep")
    c.run("create pkg")
    # print(c.out)
    assert "pkg/0.1: Created package" in c.out
