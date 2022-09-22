import platform
import re
import os
import shutil
import textwrap

import pytest

from conans.model.ref import ConanFileReference, PackageReference
from conans.test.utils.tools import TestClient, TestServer


@pytest.mark.skipif(platform.system() not in ["Linux", "Darwin"], reason="Requires Autotools")
@pytest.mark.tool_autotools()
def test_autotools_lib_template():
    client = TestClient(path_with_spaces=False)
    client.run("new hello/0.1 --template=autotools_lib")

    # Local flow works
    client.run("install . -if=install")
    client.run("build . -if=install")

    client.run("export-pkg . hello/0.1@ -if=install")
    package_id = re.search(r"Packaging to (\S+)", str(client.out)).group(1)
    pref = PackageReference(ConanFileReference.loads("hello/0.1"), package_id)
    package_folder = client.cache.package_layout(pref.ref).package(pref)
    assert os.path.exists(os.path.join(package_folder, "include", "hello.h"))

    # Create works
    client.run("create .")
    assert "hello/0.1: Hello World Release!" in client.out

    client.run("create . -s build_type=Debug")
    assert "hello/0.1: Hello World Debug!" in client.out

    # Create + shared works
    client.save({}, clean_first=True)
    client.run("new hello/0.1 --template=autotools_lib")
    client.run("create . -o hello:shared=True")
    assert "hello/0.1: Hello World Release!" in client.out
    if platform.system() == "Darwin":
        client.run_command("otool -l test_package/build-release/main")
        assert "libhello.0.dylib" in client.out
    else:
        client.run_command("ldd test_package/build-release/main")
        assert "libhello.so.0" in client.out


@pytest.mark.skipif(platform.system() not in ["Linux", "Darwin"], reason="Requires Autotools")
@pytest.mark.tool_autotools()
def test_autotools_exe_template():
    client = TestClient(path_with_spaces=False)
    client.run("new greet/0.1 --template=autotools_exe")
    # Local flow works
    client.run("install . -if=install")
    client.run("build . -if=install")

    # Create works
    client.run("create .")
    # check that for exe's we don't add any static/shared flag
    for flag in ["--enable-static", "--disable-static", "--disable-shared", "--with-pic"]:
        assert flag not in client.out
    assert "greet/0.1: Hello World Release!" in client.out

    client.run("create . -s build_type=Debug")
    for flag in ["--enable-static", "--disable-static", "--disable-shared", "--with-pic"]:
        assert flag not in client.out
    assert "greet/0.1: Hello World Debug!" in client.out


@pytest.mark.skipif(platform.system() not in ["Darwin"], reason="Requires Autotools")
@pytest.mark.tool_autotools()
def test_autotools_relocatable_libs_darwin():
    client = TestClient(path_with_spaces=False)
    client.run("new hello/0.1 --template=autotools_lib")
    client.run("create . -o hello:shared=True")
    package_id = re.search(r"Package (\S+)", str(client.out)).group(1)
    package_id = package_id.replace("'", "")
    pref = PackageReference(ConanFileReference.loads("hello/0.1"), package_id)
    package_folder = client.cache.package_layout(pref.ref).package(pref)
    dylib = os.path.join(package_folder, "lib", "libhello.0.dylib")
    if platform.system() == "Darwin":
        client.run_command("otool -l {}".format(dylib))
        assert "@rpath/libhello.0.dylib" in client.out
        client.run_command("otool -l {}".format("test_package/build-release/main"))

    # will work because rpath set
    client.run_command("test_package/build-release/main")
    assert "hello/0.1: Hello World Release!" in client.out

    # move to another location so that the path set in the rpath does not exist
    # then the execution should fail
    shutil.move(os.path.join(package_folder, "lib"), os.path.join(client.current_folder, "tempfolder"))
    # will fail because rpath does not exist
    client.run_command("test_package/build-release/main", assert_error=True)
    assert "Library not loaded: @rpath/libhello.0.dylib" in str(client.out).replace("'", "")

    # Use DYLD_LIBRARY_PATH and should run
    client.run_command("DYLD_LIBRARY_PATH={} test_package/build-release/main".format(os.path.join(client.current_folder, "tempfolder")))
    assert "hello/0.1: Hello World Release!" in client.out


@pytest.mark.skipif(platform.system() not in ["Darwin"], reason="Requires Autotools")
@pytest.mark.tool_autotools()
def test_autotools_relocatable_libs_darwin_downloaded():
    server = TestServer([("*/*@*/*", "*")], [("*/*@*/*", "*")])
    client = TestClient(servers={"default": server}, path_with_spaces=False)
    client2 = TestClient(servers={"default": server}, path_with_spaces=False)
    assert client2.cache_folder != client.cache_folder
    client.run("new hello/0.1 --template=autotools_lib")
    client.run("create . -o hello:shared=True -tf=None")
    client.run("upload * --all -c")
    client.run("remove * -f")

    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.gnu import Autotools
        from conan.tools.layout import basic_layout

        class GreetConan(ConanFile):
            name = "greet"
            version = "1.0"
            settings = "os", "compiler", "build_type", "arch"
            exports_sources = "configure.ac", "Makefile.am", "main.cpp"
            generators = "AutotoolsDeps", "AutotoolsToolchain"

            def requirements(self):
                self.requires("hello/0.1")

            def layout(self):
                basic_layout(self)

            def build(self):
                autotools = Autotools(self)
                autotools.autoreconf()
                autotools.configure()
                autotools.make()
        """)

    main = textwrap.dedent("""
        #include "hello.h"
        int main() { hello(); }
        """)

    makefileam = textwrap.dedent("""
        bin_PROGRAMS = greet
        greet_SOURCES = main.cpp
        """)

    configureac = textwrap.dedent("""
        AC_INIT([greet], [1.0], [])
        AM_INIT_AUTOMAKE([-Wall -Werror foreign])
        AC_PROG_CXX
        AM_PROG_AR
        LT_INIT
        AC_CONFIG_FILES([Makefile])
        AC_OUTPUT
        """)

    client2.save({"conanfile.py": conanfile,
                  "main.cpp": main,
                  "makefile.am": makefileam,
                  "configure.ac": configureac})

    client2.run("install . -o hello:shared=True -r default")
    client2.run("build .")
    client2.run_command("build-release/greet")
    assert "Hello World Release!" in client2.out


@pytest.mark.skipif(platform.system() not in ["Darwin"], reason="Only affects apple platforms")
@pytest.mark.tool_autotools()
def test_autotools_fix_shared_libs():
    """
    From comments in: https://github.com/conan-io/conan/pull/11365

    Case 1:
    libopencv_core.3.4.17.dylib
    libopencv_core.3.4.dylib (symlink) -> libopencv_core.3.4.17.dylib
    libopencv_core.dylib (symlink) -> libopencv_core.3.4.dylib

    Install name in libopencv_core.3.4.17.dylib is libopencv_core.3.4.dylib NOT the dylib name
    So we have to add the rpath to that.

    Case 2:
    libopencv_core.dylib
    libopencv_imgproc.dylib

    libopencv_imgproc.dylib depends on libopencv_core.dylib and declares that dependency not using the
    @rpath, we have to make sure that we patch the dependencies in the dylibs using install_name_tool -change

    Let's create a Conan package with two libraries: bye and hello (bye depends on hello)
    and recreate this whole situation to check that we are correctly fixing the dylibs
    """
    client = TestClient(path_with_spaces=False)
    client.run("new hello/0.1 --template=autotools_lib")

    conanfile = textwrap.dedent("""
        import os

        from conan import ConanFile
        from conan.tools.gnu import AutotoolsToolchain, Autotools
        from conan.tools.layout import basic_layout
        from conan.tools.apple import fix_apple_shared_install_name


        class HelloConan(ConanFile):
            name = "hello"
            version = "0.1"
            settings = "os", "compiler", "build_type", "arch"
            options = {"shared": [True, False], "fPIC": [True, False]}
            default_options = {"shared": False, "fPIC": True}
            exports_sources = "configure.ac", "Makefile.am", "src/*"

            def layout(self):
                basic_layout(self)

            def generate(self):
                at_toolchain = AutotoolsToolchain(self)
                at_toolchain.generate()

            def build(self):
                autotools = Autotools(self)
                autotools.autoreconf()
                autotools.configure()
                autotools.make()

            def package(self):
                autotools = Autotools(self)
                autotools.install()
                # before fixing the names we try to reproduce the two cases explained
                # in the test that dylib name and install name are not the same
                self.run("install_name_tool {} -id /lib/libbye.dylib".format(os.path.join(self.package_folder,
                                                                                          "lib", "libbye.0.dylib")))
                # also change that in the libbye dependencies
                self.run("install_name_tool {} -change /lib/libhello.0.dylib /lib/libhello.dylib".format(os.path.join(self.package_folder,
                                                                                                         "lib", "libbye.0.dylib")))
                self.run("install_name_tool {} -id /lib/libhello.dylib".format(os.path.join(self.package_folder,
                                                                                            "lib","libhello.0.dylib")))
                fix_apple_shared_install_name(self)

            def package_info(self):
                self.cpp_info.libs = ["hello", "bye"]
    """)

    bye_cpp = textwrap.dedent("""
        #include <iostream>
        #include "hello.h"
        #include "bye.h"
        void bye(){
            hello();
            std::cout << "Bye, bye!" << std::endl;
        }
    """)

    bye_h = textwrap.dedent("""
        #pragma once
        void bye();
    """)

    makefile_am = textwrap.dedent("""
        lib_LTLIBRARIES = libhello.la libbye.la

        libhello_la_SOURCES = hello.cpp hello.h
        libhello_la_HEADERS = hello.h
        libhello_ladir = $(includedir)

        libbye_la_SOURCES = bye.cpp bye.h
        libbye_la_HEADERS = bye.h
        libbye_ladir = $(includedir)
        libbye_la_LIBADD = libhello.la
    """)

    test_src = textwrap.dedent("""
        #include "bye.h"
        int main() { bye(); }
    """)

    client.save({
        "src/makefile.am": makefile_am,
        "src/bye.cpp": bye_cpp,
        "src/bye.h": bye_h,
        "test_package/main.cpp": test_src,
        "conanfile.py": conanfile,
    })

    client.run("create . -o hello:shared=True -tf=None")

    package_id = re.search(r"Package (\S+)", str(client.out)).group(1)
    package_id = package_id.replace("'", "")
    pref = PackageReference(ConanFileReference.loads("hello/0.1"), package_id)
    package_folder = client.cache.package_layout(pref.ref).package(pref)

    # install name fixed
    client.run_command("otool -D {}".format(os.path.join(package_folder, "lib", "libhello.0.dylib")))
    assert "@rpath/libhello.dylib" in client.out
    client.run_command("otool -D {}".format(os.path.join(package_folder, "lib", "libbye.0.dylib")))
    assert "@rpath/libbye.dylib" in client.out

    # dependencies fixed
    client.run_command("otool -L {}".format(os.path.join(package_folder, "lib", "libbye.0.dylib")))
    assert "/lib/libhello.dylib (compatibility version 1.0.0, current version 1.0.0)" not in client.out
    assert "/lib/libbye.dylib (compatibility version 1.0.0, current version 1.0.0)" not in client.out
    assert "@rpath/libhello.dylib (compatibility version 1.0.0, current version 1.0.0)" in client.out
    assert "@rpath/libbye.dylib (compatibility version 1.0.0, current version 1.0.0)" in client.out

    client.run("test test_package hello/0.1@ -o hello:shared=True")
    assert "Bye, bye!" in client.out
