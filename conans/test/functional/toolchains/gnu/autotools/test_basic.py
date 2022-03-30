import os
import platform
import textwrap
import time

import pytest

from conan.tools.env.environment import environment_wrap_command
from conans.model.ref import ConanFileReference
from conans.test.assets.autotools import gen_makefile_am, gen_configure_ac, gen_makefile
from conans.test.assets.sources import gen_function_cpp
from conans.test.functional.utils import check_exe_run
from conans.test.utils.mocks import ConanFileMock
from conans.test.utils.tools import TestClient, TurboTestClient
from conans.util.files import touch


@pytest.mark.skipif(platform.system() not in ["Linux", "Darwin"], reason="Requires Autotools")
@pytest.mark.tool_autotools()
def test_autotools():
    client = TestClient(path_with_spaces=False)
    client.run("new hello/0.1 --template=cmake_lib")
    client.run("create .")

    main = gen_function_cpp(name="main", includes=["hello"], calls=["hello"])
    makefile_am = gen_makefile_am(main="main", main_srcs="main.cpp")
    configure_ac = gen_configure_ac()

    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.gnu import Autotools

        class TestConan(ConanFile):
            requires = "hello/0.1"
            settings = "os", "compiler", "arch", "build_type"
            exports_sources = "configure.ac", "Makefile.am", "main.cpp"
            generators = "AutotoolsDeps", "AutotoolsToolchain"

            def build(self):
                self.run("aclocal")
                self.run("autoconf")
                self.run("automake --add-missing --foreign")
                autotools = Autotools(self)
                autotools.configure()
                autotools.make()
        """)

    client.save({"conanfile.py": conanfile,
                 "configure.ac": configure_ac,
                 "Makefile.am": makefile_am,
                 "main.cpp": main}, clean_first=True)
    client.run("install .")
    client.run("build .")
    client.run_command("./main")
    cxx11_abi = 0 if platform.system() == "Linux" else None
    check_exe_run(client.out, "main", "gcc", None, "Release", "x86_64", None, cxx11_abi=cxx11_abi)
    assert "hello/0.1: Hello World Release!" in client.out


def build_windows_subsystem(profile, make_program):
    """ The AutotoolsDeps can be used also in pure Makefiles, if the makefiles follow
    the Autotools conventions
    """
    # FIXME: cygwin in CI (my local machine works) seems broken for path with spaces
    client = TestClient(path_with_spaces=False)
    client.run("new hello/0.1 --template=cmake_lib")
    # TODO: Test Windows subsystems in CMake, at least msys is broken
    os.rename(os.path.join(client.current_folder, "test_package"),
              os.path.join(client.current_folder, "test_package2"))
    client.save({"profile": profile})
    client.run("create . --profile=profile")

    main = gen_function_cpp(name="main", includes=["hello"], calls=["hello"])
    makefile = gen_makefile(apps=["app"])

    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.gnu import AutotoolsToolchain, Autotools, AutotoolsDeps

        class TestConan(ConanFile):
            requires = "hello/0.1"
            settings = "os", "compiler", "arch", "build_type"
            exports_sources = "Makefile"
            generators = "AutotoolsDeps", "AutotoolsToolchain"

            def build(self):
                autotools = Autotools(self)
                autotools.make()
        """)
    client.save({"app.cpp": main,
                 "Makefile": makefile,
                 "conanfile.py": conanfile,
                 "profile": profile}, clean_first=True)

    client.run("install . --profile=profile")
    cmd = environment_wrap_command(["conanbuildenv",
                                    "conanautotoolstoolchain",
                                    "conanautotoolsdeps"], make_program, cwd=client.current_folder)
    client.run_command(cmd)
    client.run_command("app")
    # TODO: fill compiler version when ready
    check_exe_run(client.out, "main", "gcc", None, "Release", "x86_64", None)
    assert "hello/0.1: Hello World Release!" in client.out

    client.save({"app.cpp": gen_function_cpp(name="main", msg="main2",
                                             includes=["hello"], calls=["hello"])})
    # Make sure it is newer
    t = time.time() + 1
    touch(os.path.join(client.current_folder, "app.cpp"), (t, t))

    client.run("build .")
    client.run_command("app")
    # TODO: fill compiler version when ready
    check_exe_run(client.out, "main2", "gcc", None, "Release", "x86_64", None, cxx11_abi=0)
    assert "hello/0.1: Hello World Release!" in client.out
    return client.out


@pytest.mark.tool_cygwin
@pytest.mark.skipif(platform.system() != "Windows", reason="Needs windows")
def test_autotoolsdeps_cygwin():
    gcc = textwrap.dedent("""
        [settings]
        os=Windows
        os.subsystem=cygwin
        compiler=gcc
        compiler.version=4.9
        compiler.libcxx=libstdc++
        arch=x86_64
        build_type=Release
        """)
    out = build_windows_subsystem(gcc, make_program="make")
    assert "__MSYS__" not in out
    assert "MINGW" not in out
    assert "main2 __CYGWIN__1" in out


@pytest.mark.tool_mingw64
@pytest.mark.skipif(platform.system() != "Windows", reason="Needs windows")
def test_autotoolsdeps_mingw_msys():
    gcc = textwrap.dedent("""
        [settings]
        os=Windows
        compiler=gcc
        compiler.version=4.9
        compiler.libcxx=libstdc++
        arch=x86_64
        build_type=Release
        """)
    out = build_windows_subsystem(gcc, make_program="mingw32-make")
    assert "__MSYS__" not in out
    assert "main2 __MINGW64__1" in out


@pytest.mark.tool_msys2
@pytest.mark.skipif(platform.system() != "Windows", reason="Needs windows")
def test_autotoolsdeps_msys():
    gcc = textwrap.dedent("""
        [settings]
        os=Windows
        os.subsystem=msys2
        compiler=gcc
        compiler.version=4.9
        compiler.libcxx=libstdc++
        arch=x86_64
        build_type=Release
        """)
    out = build_windows_subsystem(gcc, make_program="make")
    # Msys2 is a rewrite of Msys, using Cygwin
    assert "MINGW" not in out
    assert "main2 __MSYS__1" in out
    assert "main2 __CYGWIN__1" in out


@pytest.mark.skipif(platform.system() not in ["Linux", "Darwin"], reason="Requires Autotools")
@pytest.mark.tool_autotools()
def test_install_output_directories():
    """
    If we change the libdirs of the cpp.package, as we are doing cmake.install, the output directory
    for the libraries is changed
    """
    client = TurboTestClient(path_with_spaces=False)
    client.run("new hello/1.0 --template cmake_lib")
    client.run("create .")
    consumer_conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.gnu import Autotools

        class TestConan(ConanFile):
            requires = "hello/1.0"
            settings = "os", "compiler", "arch", "build_type"
            exports_sources = "configure.ac", "Makefile.am", "main.cpp", "consumer.h"
            generators = "AutotoolsDeps", "AutotoolsToolchain"

            def layout(self):
                self.folders.build = "."
                self.cpp.package.bindirs = ["mybin"]

            def build(self):
                self.run("aclocal")
                self.run("autoconf")
                self.run("automake --add-missing --foreign")
                autotools = Autotools(self)
                autotools.configure()
                autotools.make()
                autotools.install()
    """)

    main = gen_function_cpp(name="main", includes=["hello"], calls=["hello"])
    makefile_am = gen_makefile_am(main="main", main_srcs="main.cpp")
    configure_ac = gen_configure_ac()
    client.save({"conanfile.py": consumer_conanfile,
                 "configure.ac": configure_ac,
                 "Makefile.am": makefile_am,
                 "main.cpp": main}, clean_first=True)
    ref = ConanFileReference.loads("zlib/1.2.11")
    pref = client.create(ref, conanfile=consumer_conanfile)
    p_folder = client.cache.package_layout(pref.ref).package(pref)
    assert os.path.exists(os.path.join(p_folder, "mybin", "main"))
    assert not os.path.exists(os.path.join(p_folder, "bin"))
