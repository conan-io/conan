import os
import platform

import pytest

from conan.test.utils.mocks import ConanFileMock
from conan.tools.env.environment import environment_wrap_command
from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient


def editable_cmake(generator, build_folder=None):
    c = TestClient()
    if generator is not None:
        c.save_home({"global.conf": "tools.cmake.cmaketoolchain:generator={}".format(generator)})
    with c.chdir("dep"):
        c.run("new cmake_lib -d name=dep -d version=0.1")
    with c.chdir("pkg"):
        c.run("new cmake_exe -d name=pkg -d version=0.1 -d requires=dep/0.1")

    output_folder = '--output-folder="{}"'.format(build_folder) if build_folder else ""

    def build_dep():
        c.run("build . {}".format(output_folder))
        c.run("build . -s build_type=Debug {}".format(output_folder))

    with c.chdir("dep"):
        c.run("editable add . {}".format(output_folder))
        build_dep()

    def build_pkg(msg, build_editable=False):
        build_editable = "--build=editable" if build_editable else ""
        c.run(f"build . {build_editable}")
        folder = os.path.join("build", "Release")
        c.run_command(os.sep.join([".", folder, "pkg"]))
        assert "pkg/0.1: Hello World Release!" in c.out
        assert "{}: Hello World Release!".format(msg) in c.out
        c.run(f"build . -s build_type=Debug {build_editable}")
        folder = os.path.join("build", "Debug")
        c.run_command(os.sep.join([".", folder, "pkg"]))
        assert "pkg/0.1: Hello World Debug!" in c.out
        assert "{}: Hello World Debug!".format(msg) in c.out

    with c.chdir("pkg"):
        c.run("install . ")
        c.run("install . -s build_type=Debug")
        build_pkg("dep/0.1")

    # Do a source change in the editable!
    with c.chdir("dep"):
        f = c.load("src/dep.cpp")
        f = f.replace("dep/0.1", "SUPERDEP/0.1")
        c.save({"src/dep.cpp": f})
        build_dep()

    with c.chdir("pkg"):
        build_pkg("SUPERDEP/0.1")

    # Do a source change in the editable, but do NOT build yet
    with c.chdir("dep"):
        f = c.load("src/dep.cpp")
        f = f.replace("SUPERDEP/0.1", "MEGADEP/0.1")
        c.save({"src/dep.cpp": f})
    # And build with --build=editable
    with c.chdir("pkg"):
        build_pkg("MEGADEP/0.1", build_editable=True)

    # Check that create is still possible
    c.run("editable remove dep")
    c.run("create dep")
    c.run("create pkg")
    # print(c.out)
    assert "pkg/0.1: Created package" in c.out


@pytest.mark.skipif(platform.system() != "Windows", reason="Only windows")
@pytest.mark.parametrize("generator", [None, "MinGW Makefiles"])
@pytest.mark.tool("mingw64")
def test_editable_cmake_windows(generator):
    editable_cmake(generator)


@pytest.mark.tool("cmake")
def test_editable_cmake_windows_folders():
    build_folder = temp_folder()
    editable_cmake(generator=None, build_folder=build_folder)


@pytest.mark.skipif(platform.system() != "Linux", reason="Only linux")
@pytest.mark.parametrize("generator", [None, "Ninja", "Ninja Multi-Config"])
@pytest.mark.tool("cmake", "3.19")
def test_editable_cmake_linux(generator):
    editable_cmake(generator)


@pytest.mark.skipif(platform.system() != "Darwin", reason="Requires Macos")
@pytest.mark.parametrize("generator", [None, "Ninja", "Xcode"])
@pytest.mark.tool("cmake", "3.23")
def test_editable_cmake_osx(generator):
    editable_cmake(generator)


def editable_cmake_exe(generator):
    c = TestClient()
    if generator is not None:
        c.save_home({"global.conf": "tools.cmake.cmaketoolchain:generator={}".format(generator)})

    c.run("new cmake_exe -d name=dep -d version=0.1 -o=dep")

    def build_dep():
        c.run("build .")
        c.run("build . -s build_type=Debug")

    with c.chdir("dep"):
        c.run("editable add .")
        build_dep()

    def run_pkg(msg):
        host_arch = c.get_default_host_profile().settings['arch']
        cmd_release = environment_wrap_command(ConanFileMock(), f"conanrunenv-release-{host_arch}",
                                               c.current_folder, "dep")
        c.run_command(cmd_release)
        assert "{}: Hello World Release!".format(msg) in c.out
        cmd_release = environment_wrap_command(ConanFileMock(), f"conanrunenv-debug-{host_arch}",
                                               c.current_folder, "dep")
        c.run_command(cmd_release)
        assert "{}: Hello World Debug!".format(msg) in c.out

    with c.chdir("pkg"):
        c.run("install --requires=dep/0.1")
        c.run("install --requires=dep/0.1 -s build_type=Debug")
        run_pkg("dep/0.1")

    # Do a source change in the editable!
    with c.chdir("dep"):
        dep = c.load("src/dep.cpp")
        dep = dep.replace("dep/0.1", "SUPERDEP/0.1")
        c.save({"src/dep.cpp": dep})
        build_dep()

    with c.chdir("pkg"):
        run_pkg("SUPERDEP/0.1")


@pytest.mark.skipif(platform.system() != "Windows", reason="Only windows")
@pytest.mark.parametrize("generator", [None, "MinGW Makefiles"])
@pytest.mark.tool("mingw64")
def test_editable_cmake_windows_exe(generator):
    editable_cmake_exe(generator)


@pytest.mark.skipif(platform.system() != "Linux", reason="Only linux")
@pytest.mark.parametrize("generator", [None, "Ninja", "Ninja Multi-Config"])
@pytest.mark.tool("cmake", "3.19")
def test_editable_cmake_linux_exe(generator):
    editable_cmake_exe(generator)


@pytest.mark.skipif(platform.system() != "Darwin", reason="Requires Macos")
@pytest.mark.parametrize("generator", [None, "Ninja", "Xcode"])
@pytest.mark.tool("cmake", "3.23")
def test_editable_cmake_osx_exe(generator):
    editable_cmake_exe(generator)
