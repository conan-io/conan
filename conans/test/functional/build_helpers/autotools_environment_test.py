import os
import platform
import unittest

from conans.client import tools
from conans.model.ref import ConanFileReference, PackageReference
from conans.paths import CONANFILE
from conans.test.unittests.util.tools_test import RunnerMock
from conans.test.utils.conanfile import MockConanfile
from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestClient

default_dirs_flags = ["--bindir", "--libdir", "--includedir", "--datarootdir", "--libdir",
                      "--sbindir", "--oldincludedir", "--libexecdir"]


class MockConanfileWithOutput(MockConanfile):
    def run(self, *args, **kwargs):
        if self.runner:
            self.runner(*args, **kwargs)


class RunnerMockWithHelp(RunnerMock):

    def __init__(self, return_ok=True, available_args=None):
        self.command_called = None
        self.return_ok = return_ok
        self.available_args = available_args or []

    def __call__(self, command, output=None, win_bash=False, subsystem=None):  # @UnusedVariable
        if "configure --help" in command:
            output.write(" ".join(self.available_args))
        else:
            return super(RunnerMockWithHelp, self).__call__(command, output, win_bash, subsystem)


class AutoToolsConfigureTest(unittest.TestCase):

    def _set_deps_info(self, conanfile):
        conanfile.deps_cpp_info.include_paths.append("path/includes")
        conanfile.deps_cpp_info.include_paths.append("other\include\path")
        # To test some path in win, to be used with MinGW make or MSYS etc
        conanfile.deps_cpp_info.lib_paths.append("one\lib\path")
        conanfile.deps_cpp_info.libs.append("onelib")
        conanfile.deps_cpp_info.libs.append("twolib")
        conanfile.deps_cpp_info.defines.append("onedefinition")
        conanfile.deps_cpp_info.defines.append("twodefinition")
        conanfile.deps_cpp_info.cflags.append("a_c_flag")
        conanfile.deps_cpp_info.cppflags.append("a_cpp_flag")
        conanfile.deps_cpp_info.sharedlinkflags.append("shared_link_flag")
        conanfile.deps_cpp_info.exelinkflags.append("exe_link_flag")
        conanfile.deps_cpp_info.sysroot = "/path/to/folder"

    @unittest.skipUnless(platform.system() == "Linux", "Requires make")
    def autotools_real_install_dirs_test(self):
        body = r"""#include "hello.h"
#include <iostream>
using namespace std;

void hello()
{
    cout << "Hola Mundo!";
}
"""
        header = """
#pragma once
void hello();
"""
        main = """
#include "hello.h"

int main()
{
    hello();
    return 0;
}
"""
        conanfile = """
from conans import ConanFile, AutoToolsBuildEnvironment, tools

class TestConan(ConanFile):
    name = "test"
    version = "1.0"
    settings = "os", "compiler", "arch", "build_type"
    exports_sources = "*"

    def build(self):
        makefile_am = '''
bin_PROGRAMS = main
lib_LIBRARIES = libhello.a
libhello_a_SOURCES = hello.cpp
main_SOURCES = main.cpp
main_LDADD = libhello.a
'''
        configure_ac = '''
AC_INIT([main], [1.0], [luism@jfrog.com])
AM_INIT_AUTOMAKE([-Wall -Werror foreign])
AC_PROG_CXX
AC_PROG_RANLIB
AM_PROG_AR
AC_CONFIG_FILES([Makefile])
AC_OUTPUT
'''
        tools.save("Makefile.am", makefile_am)
        tools.save("configure.ac", configure_ac)
        self.run("aclocal")
        self.run("autoconf")
        self.run("automake --add-missing --foreign")
        autotools = AutoToolsBuildEnvironment(self)
        autotools.configure()
        autotools.make()
        autotools.install()

    def package_id(self):
        # easier to have same package_id for the test
        self.info.header_only()
"""
        client = TestClient()
        client.save({"conanfile.py": conanfile,
                     "main.cpp": main,
                     "hello.h": header,
                     "hello.cpp": body})
        client.run("create . danimtb/testing")
        pkg_path = client.client_cache.package(
                PackageReference.loads(
                        "test/1.0@danimtb/testing:%s" % NO_SETTINGS_PACKAGE_ID))

        [self.assertIn(folder, os.listdir(pkg_path)) for folder in ["lib", "bin"]]

        new_conanfile = conanfile.replace("autotools.configure()",
                                          "autotools.configure(args=['--bindir=${prefix}/superbindir', '--libdir=${prefix}/superlibdir'])")
        client.save({"conanfile.py": new_conanfile})
        client.run("create . danimtb/testing")
        [self.assertIn(folder, os.listdir(pkg_path)) for folder in ["superlibdir", "superbindir"]]
        [self.assertNotIn(folder, os.listdir(pkg_path)) for folder in ["lib", "bin"]]

    def test_pkg_config_paths(self):
        if platform.system() == "Windows":
            return
        client = TestClient()
        conanfile = """
from conans import ConanFile, tools, AutoToolsBuildEnvironment

class HelloConan(ConanFile):
    name = "Hello"
    version = "1.2.1"
    generators = %s

    def build(self):
        tools.save("configure", "printenv")
        self.run("chmod +x configure")
        autot = AutoToolsBuildEnvironment(self)
        autot.configure(%s)

"""

        client.save({CONANFILE: conanfile % ("'txt'", "")})
        client.run("create . conan/testing")
        self.assertNotIn("PKG_CONFIG_PATH=", client.out)

        ref = ConanFileReference.loads("Hello/1.2.1@conan/testing")
        builds_folder = client.client_cache.builds(ref)
        bf = os.path.join(builds_folder, os.listdir(builds_folder)[0])

        client.save({CONANFILE: conanfile % ("'pkg_config'", "")})
        client.run("create . conan/testing")
        self.assertIn("PKG_CONFIG_PATH=%s" % bf, client.out)

        # The previous values in the environment should be kept too
        with tools.environment_append({"PKG_CONFIG_PATH": "Some/value"}):
            client.run("create . conan/testing")
            self.assertIn("PKG_CONFIG_PATH=%s:Some/value" % bf, client.out)

        client.save({CONANFILE: conanfile % ("'pkg_config'",
                                             "pkg_config_paths=['/tmp/hello', 'foo']")})
        client.run("create . conan/testing")
        self.assertIn("PKG_CONFIG_PATH=/tmp/hello:%s/foo" % bf, client.out)

        # The previous values in the environment should be kept too
        with tools.environment_append({"PKG_CONFIG_PATH": "Some/value"}):
            client.run("create . conan/testing")
            self.assertIn("PKG_CONFIG_PATH=/tmp/hello:%s/foo:Some/value" % bf, client.out)
