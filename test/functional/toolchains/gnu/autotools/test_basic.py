import os
import platform
import textwrap
import time
import re

import pytest

from conan.tools.env.environment import environment_wrap_command
from conans.model.recipe_ref import RecipeReference
from conan.test.assets.autotools import gen_makefile_am, gen_configure_ac, gen_makefile
from conan.test.assets.genconanfile import GenConanfile
from conan.test.assets.sources import gen_function_cpp
from test.functional.utils import check_exe_run, check_vs_runtime
from conan.test.utils.tools import TestClient, TurboTestClient


@pytest.mark.skipif(platform.system() not in ["Linux", "Darwin"], reason="Requires Autotools")
@pytest.mark.tool("autotools")
def test_autotools():
    client = TestClient(path_with_spaces=False)
    client.run("new cmake_lib -d name=hello -d version=0.1")
    client.run("create .")

    main = gen_function_cpp(name="main", includes=["hello"], calls=["hello"])
    makefile_am = gen_makefile_am(main="main", main_srcs="main.cpp")
    configure_ac = gen_configure_ac()

    conanfile = textwrap.dedent("""
        from conan import ConanFile
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
    cxx11_abi = 1 if platform.system() == "Linux" else None
    compiler = "gcc" if platform.system() == "Linux" else "apple-clang"
    host_arch = client.get_default_host_profile().settings['arch']
    check_exe_run(client.out, "main", compiler, None, "Release", host_arch, None, cxx11_abi=cxx11_abi)
    assert "hello/0.1: Hello World Release!" in client.out


def build_windows_subsystem(profile, make_program, subsystem):
    """ The AutotoolsDeps can be used also in pure Makefiles, if the makefiles follow
    the Autotools conventions

    This doesn't run in bash at all, not win_bash, pure Windows terminal
    """
    # FIXME: cygwin in CI (my local machine works) seems broken for path with spaces
    client = TestClient(path_with_spaces=False)
    client.run("new cmake_lib -d name=hello -d version=0.1")
    # TODO: Test Windows subsystems in CMake, at least msys is broken
    os.rename(os.path.join(client.current_folder, "test_package"),
              os.path.join(client.current_folder, "test_package2"))
    client.save({"profile": profile})
    client.run("create . --profile=profile")

    main = gen_function_cpp(name="main", includes=["hello"], calls=["hello"])
    makefile = gen_makefile(apps=["app"])

    conanfile = textwrap.dedent("""
        from conan import ConanFile
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
                                    "conanautotoolsdeps"], client.current_folder, make_program)
    client.run_command(cmd)
    client.run_command("app")
    # TODO: fill compiler version when ready
    check_exe_run(client.out, "main", "gcc", None, "Release", "x86_64", None, subsystem=subsystem)
    assert "hello/0.1: Hello World Release!" in client.out
    check_vs_runtime("app.exe", client, vs_version="15", build_type="Release", architecture="amd64",
                     static_runtime=False, subsystem=subsystem)

    client.save({"app.cpp": gen_function_cpp(name="main", msg="main2",
                                             includes=["hello"], calls=["hello"])})
    # Make sure it is newer
    t = time.time() + 1
    os.utime(os.path.join(client.current_folder, "app.cpp"), (t, t))

    client.run("build . --profile=profile")
    client.run_command("app")
    # TODO: fill compiler version when ready
    check_exe_run(client.out, "main2", "gcc", None, "Release", "x86_64", None, cxx11_abi=0,
                  subsystem=subsystem)
    assert "hello/0.1: Hello World Release!" in client.out
    return client.out


@pytest.mark.tool("cygwin")
@pytest.mark.skipif(platform.system() != "Windows", reason="Needs windows")
def test_autotoolsdeps_cygwin():
    # TODO: This test seems broken locally, need to really verify is passing in CI
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
    build_windows_subsystem(gcc, make_program="make", subsystem="cygwin")


@pytest.mark.tool("mingw64")
@pytest.mark.skipif(platform.system() != "Windows", reason="Needs windows")
def test_autotoolsdeps_mingw_msys():
    # FIXME: Missing subsystem to model mingw libstdc++
    gcc = textwrap.dedent("""
        [settings]
        os=Windows
        compiler=gcc
        compiler.version=4.9
        compiler.libcxx=libstdc++
        arch=x86_64
        build_type=Release
        """)
    build_windows_subsystem(gcc, make_program="mingw32-make", subsystem="mingw64")


@pytest.mark.tool("msys2")
@pytest.mark.skipif(platform.system() != "Windows", reason="Needs windows")
# If we use the cmake inside msys2, it fails, so better force our own cmake
@pytest.mark.tool("cmake", "3.19")
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
    build_windows_subsystem(gcc, make_program="make", subsystem="msys2")


@pytest.mark.skipif(platform.system() not in ["Linux", "Darwin"], reason="Requires Autotools")
@pytest.mark.tool("autotools")
def test_install_output_directories():
    """
    If we change the libdirs of the cpp.package, as we are doing cmake.install, the output directory
    for the libraries is changed
    """
    client = TurboTestClient(path_with_spaces=False)
    client.run("new cmake_lib -d name=hello -d version=1.0")
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
    ref = RecipeReference.loads("zlib/1.2.11")
    pref = client.create(ref, conanfile=consumer_conanfile)
    p_folder = client.get_latest_pkg_layout(pref).package()
    assert os.path.exists(os.path.join(p_folder, "mybin", "main"))
    assert not os.path.exists(os.path.join(p_folder, "bin"))


@pytest.mark.skipif(platform.system() not in ["Linux", "Darwin"], reason="Requires Autotools")
@pytest.mark.tool("autotools")
def test_autotools_with_pkgconfigdeps():
    client = TestClient(path_with_spaces=False)
    client.run("new cmake_lib -d name=hello -d version=1.0")
    client.run("create .")

    consumer_conanfile = textwrap.dedent("""
        [requires]
        hello/1.0
        [generators]
        AutotoolsToolchain
        PkgConfigDeps
    """)
    client.save({"conanfile.txt": consumer_conanfile}, clean_first=True)
    client.run("install .")

    client.run_command(". ./conanautotoolstoolchain.sh && "
                       "pkg-config --cflags hello && "
                       "pkg-config --libs-only-l hello && "
                       "pkg-config --libs-only-L --libs-only-other hello")

    assert re.search("I.*/p/include", str(client.out))
    assert "-lhello" in client.out
    assert re.search("L.*/p/lib", str(client.out))


@pytest.mark.skipif(platform.system() not in ["Linux", "Darwin"], reason="Requires Autotools")
@pytest.mark.tool("autotools")
def test_autotools_option_checking():
    # https://github.com/conan-io/conan/issues/11265
    client = TestClient(path_with_spaces=False)
    client.run("new autotools_lib -d name=mylib -d version=1.0")
    conanfile = textwrap.dedent("""
        import os

        from conan import ConanFile
        from conan.tools.gnu import AutotoolsToolchain, Autotools
        from conan.tools.layout import basic_layout
        from conan.tools.build import cross_building


        class MylibTestConan(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            generators = "AutotoolsDeps"

            def requirements(self):
                self.requires(self.tested_reference_str)

            def generate(self):
                at_toolchain = AutotoolsToolchain(self)
                # we override the default shared/static flags here
                at_toolchain.configure_args = ['--enable-option-checking=fatal']
                at_toolchain.generate()

            def build(self):
                autotools = Autotools(self)
                autotools.autoreconf()
                autotools.configure()
                autotools.make()

            def layout(self):
                basic_layout(self)

            def test(self):
                if not cross_building(self):
                    cmd = os.path.join(self.cpp.build.bindirs[0], "main")
                    self.run(cmd, env="conanrun")
            """)

    client.save({"test_package/conanfile.py": conanfile})
    client.run("create . -tf=\"\"")

    # check that the shared flags are not added to the exe's configure, making it fail
    client.run("test test_package mylib/1.0@")
    assert "configure: error: unrecognized options: --disable-shared, --enable-static, --with-pic" \
           not in client.out


@pytest.mark.skipif(platform.system() not in ["Linux", "Darwin"], reason="Requires Autotools")
@pytest.mark.tool("autotools")
def test_autotools_arguments_override():
    client = TestClient(path_with_spaces=False)
    client.run("new autotools_lib -d name=mylib -d version=1.0")
    conanfile = textwrap.dedent("""
        import os

        from conan import ConanFile
        from conan.tools.gnu import AutotoolsToolchain, Autotools
        from conan.tools.layout import basic_layout


        class MyLibConan(ConanFile):
            name = "mylib"
            version = "1.0"

            # Binary configuration
            settings = "os", "compiler", "build_type", "arch"

            exports_sources = "configure.ac", "Makefile.am", "src/*"

            def config_options(self):
                if self.settings.os == "Windows":
                    self.options.rm_safe("fPIC")

            def layout(self):
                basic_layout(self)

            def generate(self):
                at_toolchain = AutotoolsToolchain(self)
                at_toolchain.configure_args = ['--disable-shared']
                at_toolchain.make_args = ['--warn-undefined-variables']
                at_toolchain.autoreconf_args = ['--verbose']
                at_toolchain.generate()

            def build(self):
                autotools = Autotools(self)
                autotools.autoreconf(args=['--install'])
                autotools.configure(args=['--prefix=/', '--libdir=${prefix}/customlibfolder',
                                          '--includedir=${prefix}/customincludefolder',
                                          '--pdfdir=${prefix}/res'])
                autotools.make(args=['--keep-going'])

            def package(self):
                autotools = Autotools(self)
                autotools.install(args=['DESTDIR={}/somefolder'.format(self.package_folder)])

            def package_info(self):
                self.cpp_info.libs = ["mylib"]
                self.cpp_info.libdirs = ["somefolder/customlibfolder"]
                self.cpp_info.includedirs = ["somefolder/customincludefolder"]
        """)

    client.save({"conanfile.py": conanfile})
    client.run("create . -tf=\"\"")

    # autoreconf args --force that is default should not be there
    assert "--force" not in client.out
    assert "--install" in client.out

    # we override the default DESTDIR in the install
    assert re.search("^.*make install .*DESTDIR=(.*)/somefolder.*$", str(client.out), re.MULTILINE)

    # we did override the default install args
    for arg in ['--bindir=${prefix}/bin', '--sbindir=${prefix}/bin',
                '--libdir=${prefix}/lib', '--includedir=${prefix}/include',
                '--oldincludedir=${prefix}/include', '--datarootdir=${prefix}/res']:
        assert arg not in client.out

    # and use our custom arguments
    for arg in ['--prefix=/', '--libdir=${prefix}/customlibfolder',
                '--includedir=${prefix}/customincludefolder', '--pdfdir=${prefix}/res']:
        assert arg in client.out

    # check the other arguments we set are there
    assert "--disable-shared" in client.out
    assert "--warn-undefined-variables" in client.out
    assert "--verbose" in client.out
    assert "--keep-going" in client.out

    client.run("test test_package mylib/1.0@")
    assert "mylib/1.0: Hello World Release!" in client.out


@pytest.mark.skipif(platform.system() != "Windows", reason="Only MSVC")
def test_msvc_extra_flag():
    profile = textwrap.dedent("""
        [settings]
        os=Windows
        compiler=msvc
        compiler.version=193
        compiler.runtime=dynamic
        arch=x86_64
        build_type=Release
        """)
    client = TestClient()
    conanfile = GenConanfile().with_settings("os", "arch", "compiler", "build_type")\
        .with_generator("AutotoolsToolchain")
    client.save({"conanfile.py": conanfile,
                "profile": profile})
    client.run("install . --profile:build=profile --profile:host=profile")
    toolchain = client.load("conanautotoolstoolchain{}".format('.bat'))
    assert 'set "CXXFLAGS=%CXXFLAGS% -MD -O2 -Ob2 -FS"' in toolchain
    assert 'set "CFLAGS=%CFLAGS% -MD -O2 -Ob2 -FS"' in toolchain

    # now verify not duplicated
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.gnu import AutotoolsToolchain
        class Pkg(ConanFile):
            settings = "os", "arch", "compiler", "build_type"
            def generate(self):
                tc = AutotoolsToolchain(self)
                tc.extra_cxxflags.append("-FS")
                tc.extra_cflags.append("-FS")
                tc.generate()
                """)
    client.save({"conanfile.py": conanfile})
    client.run("install . --profile:build=profile --profile:host=profile")
    toolchain = client.load("conanautotoolstoolchain{}".format('.bat'))
    assert 'set "CXXFLAGS=%CXXFLAGS% -MD -O2 -Ob2 -FS"' in toolchain
    assert 'set "CFLAGS=%CFLAGS% -MD -O2 -Ob2 -FS"' in toolchain
