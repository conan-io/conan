import os
import platform
import unittest

from conans.model.ref import ConanFileReference
from conans.paths import CONANFILE
from conans.test.utils.tools import TestClient
from conans.tools import unix_path
from conans.util.files import md5sum

mylibh = '''
double mean(double a, double b);
'''
conanfile = '''
from conans import ConanFile

class ConanMeanLib(ConanFile):
    name = "Mean"
    version = "0.1"
    exports_sources = "mean*"
    settings = "os", "compiler", "build_type", "arch"
    options = {"activate_define": [True, False], "optimize": [True, False]}
    default_options = """activate_define=True
optimize=False
"""
    generators = "gcc"

    def build(self):
        self.output.info("Running source!")
        self.run("c++ -c -o mean.o @conanbuildinfo.gcc mean.cpp")
        self.run("ar rcs libmean.a mean.o")

    def package(self):
        self.copy("*.h", dst="include")
        self.copy("*.a", dst="lib")

    def package_info(self):
        self.cpp_info.libs.append("mean")
        if self.options.activate_define:
            self.cpp_info.defines.append("ACTIVE_VAR=1")
        if self.options.optimize:
            self.cpp_info.cflags.append("-O2")
'''

mylib = '''
double mean(double a, double b) {
  return (a+b) / 2;
}
'''

example = '''
#include "mean.h"
#include <iostream>

int main(){
    std::cout << mean(10, 20) << std::endl;
    #ifdef ACTIVE_VAR
    std::cout << "Active var!!!" << std::endl;
    #endif
}
    '''


class BuildEnvironmenTest(unittest.TestCase):

    def test_gcc_and_environment(self):
        if platform.system() == "SunOS":
            return  # If is using sun-cc the gcc generator doesn't work

        # CREATE A DUMMY LIBRARY WITH GCC (could be generated with other build system)
        client = TestClient()
        client.save({CONANFILE: conanfile, "mean.cpp": mylib, "mean.h": mylibh})
        client.run("export lasote/stable")
        client.run("install Mean/0.1@lasote/stable --build")

        # Reuse the mean library using only the generator

        reuse_gcc_conanfile = '''
import platform
from conans import ConanFile
from conans.tools import environment_append

class ConanReuseLib(ConanFile):

    requires = "Mean/0.1@lasote/stable"
    generators = "gcc"
    settings = "os", "compiler", "build_type", "arch"

    def build(self):


        self.run("c++ example.cpp @conanbuildinfo.gcc -o mean_exe ")
        self.run("./mean_exe" if platform.system() != "Windows" else "mean_exe")
'''

        client.save({CONANFILE: reuse_gcc_conanfile, "example.cpp": example})
        client.run("install . --build missing")
        client.run("build .")

        self.assertIn("15", client.user_io.out)
        self.assertIn("Active var!!!", client.user_io.out)

        client.run("install . --build missing -o Mean:activate_define=False")
        client.run("build .")
        self.assertIn("15", client.user_io.out)
        self.assertNotIn("Active var!!!", client.user_io.out)

        if platform.system() != "Windows":  # MinGW 32 bits apps not running correctly
            client.run("install . --build missing -o Mean:activate_define=False -s arch=x86")
            client.run("build .")
            md5_binary = md5sum(os.path.join(client.current_folder, "mean_exe"))

            # Pass the optimize option that will append a cflag to -O2, the binary will be different
            client.run("install . --build missing -o Mean:activate_define=False -o Mean:optimize=True -s arch=x86")
            client.run("build .")
            md5_binary2 = md5sum(os.path.join(client.current_folder, "mean_exe"))

            self.assertNotEquals(md5_binary, md5_binary2)

            # Rebuid the same binary, same md5sum
            client.run("install . --build missing -o Mean:activate_define=False -o Mean:optimize=True -s arch=x86")
            client.run("build .")
            md5_binary = md5sum(os.path.join(client.current_folder, "mean_exe"))

            self.assertEquals(md5_binary, md5_binary2)

    def run_in_windows_bash_test(self):
        if platform.system() != "Windows":
            return
        conanfile = '''
from conans import ConanFile, tools

class ConanBash(ConanFile):
    name = "bash"
    version = "0.1"
    settings = "os", "compiler", "build_type", "arch"

    def build(self):
        tools.run_in_windows_bash(self, "pwd")

        '''
        client = TestClient()
        client.save({CONANFILE: conanfile})
        client.run("export lasote/stable")
        client.run("install bash/0.1@lasote/stable --build")
        expected_curdir_base = unix_path(client.client_cache.conan(ConanFileReference.loads("bash/0.1@lasote/stable")))
        self.assertIn(expected_curdir_base, client.user_io.out)

    def use_build_virtualenv_test(self):
        if platform.system() != "Linux":
            return
        client = TestClient(path_with_spaces=False)
        client.save({CONANFILE: conanfile, "mean.cpp": mylib, "mean.h": mylibh})
        client.run("export lasote/stable")

        makefile_am = '''
bin_PROGRAMS = main
main_SOURCES = main.cpp
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

        reuse_conanfile = '''
import platform
from conans import ConanFile

class ConanReuseLib(ConanFile):

    requires = "Mean/0.1@lasote/stable"
    generators = "virtualbuildenv"
    settings = "os", "compiler", "build_type", "arch"
    exports_sources = "*"

    def build(self):
        self.run("aclocal")
        self.run("autoconf")
        self.run("automake --add-missing --foreign")
        self.run("ls")
        self.run("bash -c 'source activate_build.sh && ./configure'")
        self.run("bash -c 'source activate_build.sh && make'")
        self.run("./main")
'''
        client.save({CONANFILE: reuse_conanfile,
                     "Makefile.am": makefile_am,
                     "configure.ac": configure_ac,
                     "main.cpp": example})
        client.run("install --build missing")
        client.run("build .")
        self.assertIn("15", client.user_io.out)
