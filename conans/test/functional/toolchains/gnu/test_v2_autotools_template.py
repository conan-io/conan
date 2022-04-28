import platform
import re
import os
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
    assert "greet/0.1: Hello World Release!" in client.out

    client.run("create . -s build_type=Debug")
    assert "greet/0.1: Hello World Debug!" in client.out


@pytest.mark.skipif(platform.system() not in ["Darwin"], reason="Requires Autotools")
@pytest.mark.tool_autotools()
def test_autotools_relocatable_mac():
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

        class HelloConan(ConanFile):
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
        bin_PROGRAMS = hello
        hello_SOURCES = main.cpp
        """)

    configureac = textwrap.dedent("""
        AC_INIT([hello], [1.0], [])
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

    client2.run("create . -o hello:shared=True -r default")
