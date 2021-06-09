import os
import platform

import pytest

from conans.test.assets.pkg_cmake import pkg_cmake, pkg_cmake_app
from conans.test.assets.sources import gen_function_cpp
from conans.test.utils.tools import TestClient


@pytest.mark.parametrize("generator", {"Windows": [None, "MinGW Makefiles"],
                                       "Darwin": [None, "Ninja", "Xcode"],
                                       "Linux": [None, "Ninja", "Ninja Multi-Config"]}
                         .get(platform.system()))
def test_editable_cmake(generator):
    multi = (generator is None and platform.system() == "Windows") or \
            generator in ("Ninja Multi-Config", "Xcode")
    c = TestClient()
    if generator is not None:
        c.save({"global.conf": "tools.cmake.cmaketoolchain:generator={}".format(generator)},
               path=os.path.join(c.cache.cache_folder))
    c.save(pkg_cmake("dep", "0.1"), path=os.path.join(c.current_folder, "dep"))
    c.save(pkg_cmake_app("pkg", "0.1", requires=["dep/0.1"]),
           path=os.path.join(c.current_folder, "pkg"))

    with c.chdir("dep"):
        c.run("editable add . dep/0.1@")
        c.run("install .")
        c.run("build .")
        c.run("install . -s build_type=Debug")
        c.run("build .")

    def build_pkg(msg):
        c.run("build . -if=install_release")
        folder = os.path.join("build", "Release") if multi else "cmake-build-release"
        c.run_command(os.sep.join([".", folder, "pkg"]))
        assert "main: Release!" in c.out
        assert "{}: Release!".format(msg) in c.out
        c.run("build . -if=install_debug")
        folder = os.path.join("build", "Debug") if multi else "cmake-build-debug"
        c.run_command(os.sep.join([".", folder, "pkg"]))
        assert "main: Debug!" in c.out
        assert "{}: Debug!".format(msg) in c.out

    with c.chdir("pkg"):
        c.run("install . -if=install_release")
        c.run("install . -if=install_debug -s build_type=Debug")
        build_pkg("dep")

    # Do a source change in the editable!
    with c.chdir("dep"):
        c.save({"src/dep.cpp": gen_function_cpp(name="dep", msg="SUPERDEP")})
        c.run("install .")
        c.run("build .")
        c.run("install . -s build_type=Debug")
        c.run("build .")

    with c.chdir("pkg"):
        build_pkg("SUPERDEP")

    # Check that create is still possible
    c.run("editable remove dep/0.1@")
    c.run("create dep")
    c.run("create pkg")
    # print(c.out)
    assert "pkg/0.1: Created package" in c.out
