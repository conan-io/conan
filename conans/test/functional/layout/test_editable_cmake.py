import os
import platform

import pytest

from conan.tools.env.environment import environment_wrap_command
from conans.test.assets.pkg_cmake import pkg_cmake, pkg_cmake_app
from conans.test.assets.sources import gen_function_cpp
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient


def editable_cmake(generator, build_folder=None):
    c = TestClient()
    if generator is not None:
        c.save({"global.conf": "tools.cmake.cmaketoolchain:generator={}".format(generator)},
               path=os.path.join(c.cache.cache_folder))
    c.save(pkg_cmake("dep", "0.1"), path=os.path.join(c.current_folder, "dep"))
    c.save(pkg_cmake_app("pkg", "0.1", requires=["dep/0.1"]),
           path=os.path.join(c.current_folder, "pkg"))

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
        assert "{}: Release!".format(msg) in c.out
        c.run("build . -if=install_debug")
        folder = os.path.join("build", "Debug")
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
        build_dep()

    with c.chdir("pkg"):
        build_pkg("SUPERDEP")

    # Check that create is still possible
    c.run("editable remove dep/0.1@")
    c.run("create dep")
    c.run("create pkg")
    # print(c.out)
    assert "pkg/0.1: Created package" in c.out


@pytest.mark.skipif(platform.system() != "Windows", reason="Only windows")
@pytest.mark.parametrize("generator", [None, "MinGW Makefiles"])
@pytest.mark.tool_mingw64
def test_editable_cmake_windows(generator):
    editable_cmake(generator)


def test_editable_cmake_windows_folders():
    build_folder = temp_folder()
    editable_cmake(generator=None, build_folder=build_folder)


@pytest.mark.skipif(platform.system() != "Linux", reason="Only linux")
@pytest.mark.parametrize("generator", [None, "Ninja", "Ninja Multi-Config"])
def test_editable_cmake_linux(generator):
    editable_cmake(generator)


@pytest.mark.skipif(platform.system() != "Darwin", reason="Requires Macos")
@pytest.mark.parametrize("generator", [None, "Ninja", "Xcode"])
@pytest.mark.tool_cmake(version="3.19")
def test_editable_cmake_osx(generator):
    editable_cmake(generator)


def editable_cmake_exe(generator):
    # This test works because it is not multi-config or single config, but explicit in
    # --install folder
    c = TestClient()
    if generator is not None:
        c.save({"global.conf": "tools.cmake.cmaketoolchain:generator={}".format(generator)},
               path=os.path.join(c.cache.cache_folder))
    c.save(pkg_cmake("dep", "0.1", exe=True), path=os.path.join(c.current_folder, "dep"))

    def build_dep():
        c.run("install . -o dep:shared=True -if=install_release")
        c.run("build . -if=install_release")
        c.run("install . -s build_type=Debug -o dep:shared=True -if=install_debug")
        c.run("build . -if=install_debug")

    with c.chdir("dep"):
        c.run("editable add . dep/0.1@")
        build_dep()

    def run_pkg(msg):
        host_arch = c.get_default_host_profile().settings['arch']
        # FIXME: This only works with ``--install-folder``, layout() will break this
        cmd_release = environment_wrap_command(f"conanrunenv-release-{host_arch}", c.current_folder,
                                               "dep_app",)
        c.run_command(cmd_release)
        assert "{}: Release!".format(msg) in c.out
        cmd_release = environment_wrap_command(f"conanrunenv-debug-{host_arch}", c.current_folder,
                                               "dep_app", )
        c.run_command(cmd_release)
        assert "{}: Debug!".format(msg) in c.out

    with c.chdir("pkg"):
        c.run("install dep/0.1@ -o dep:shared=True -g VirtualRunEnv")
        c.run("install dep/0.1@ -o dep:shared=True -s build_type=Debug -g VirtualRunEnv")
        run_pkg("dep")

    # Do a source change in the editable!
    with c.chdir("dep"):
        c.save({"src/dep.cpp": gen_function_cpp(name="dep", msg="SUPERDEP")})
        build_dep()

    with c.chdir("pkg"):
        run_pkg("SUPERDEP")


@pytest.mark.skipif(platform.system() != "Windows", reason="Only windows")
@pytest.mark.parametrize("generator", [None, "MinGW Makefiles"])
@pytest.mark.tool_mingw64
def test_editable_cmake_windows_exe(generator):
    editable_cmake_exe(generator)


@pytest.mark.skipif(platform.system() != "Linux", reason="Only linux")
@pytest.mark.parametrize("generator", [None, "Ninja", "Ninja Multi-Config"])
def test_editable_cmake_linux_exe(generator):
    editable_cmake_exe(generator)


@pytest.mark.skipif(platform.system() != "Darwin", reason="Requires Macos")
@pytest.mark.parametrize("generator", [None, "Ninja", "Xcode"])
@pytest.mark.tool_cmake(version="3.19")
def test_editable_cmake_osx_exe(generator):
    editable_cmake_exe(generator)
