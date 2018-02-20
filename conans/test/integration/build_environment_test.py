import platform
import unittest

from conans.paths import CONANFILE
from conans.test.utils.tools import TestClient

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

    def use_build_virtualenv_test(self):
        if platform.system() != "Linux":
            return
        client = TestClient(path_with_spaces=False)
        client.save({CONANFILE: conanfile, "mean.cpp": mylib, "mean.h": mylibh})
        client.run("export . lasote/stable")

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
        client.run("install . --build missing")
        client.run("build .")
        self.assertIn("15", client.user_io.out)
