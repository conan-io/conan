import platform
import textwrap
import unittest
from textwrap import dedent

import pytest

from conans.paths import CONANFILE
from conans.test.assets.autotools import gen_makefile_am, gen_configure_ac
from conans.test.utils.tools import TestClient
from conans.test.assets.cpp_test_files import cpp_hello_conan_files


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

    @pytest.mark.skipif(platform.system() != "Linux", reason="Requires Linux")
    @pytest.mark.tool_autotools
    def test_use_build_virtualenv(self):
        client = TestClient(path_with_spaces=False)
        client.save({CONANFILE: conanfile, "mean.cpp": mylib, "mean.h": mylibh})
        client.run("export . lasote/stable")

        makefile_am = gen_makefile_am(main="main", main_srcs="main.cpp")
        configure_ac = gen_configure_ac()

        reuse_conanfile = textwrap.dedent('''
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
            ''')
        client.save({CONANFILE: reuse_conanfile,
                     "Makefile.am": makefile_am,
                     "configure.ac": configure_ac,
                     "main.cpp": example})
        client.run("install . --build missing")
        client.run("build .")
        self.assertIn("15", client.out)

    @pytest.mark.skipif(platform.system() != "Windows", reason="Requires windows")
    def test_use_build_virtualenv_windows(self):
        files = cpp_hello_conan_files("hello", "0.1",  use_cmake=False, with_exe=False)
        client = TestClient(path_with_spaces=False)
        client.save(files)
        client.run("create . user/testing")
        files = cpp_hello_conan_files("hello2", "0.1", deps=["hello/0.1@user/testing"],
                                      use_cmake=False, with_exe=False)
        client.save(files, clean_first=True)
        client.run("create . user/testing")

        reuse_conanfile = dedent('''
            from conans import ConanFile

            class ConanReuseLib(ConanFile):
                requires = "hello2/0.1@user/testing"
                generators = "virtualbuildenv"
                settings = "os", "compiler", "build_type", "arch"

                def build(self):
                    self.run('activate_build.bat && cl /c /EHsc hello.cpp')
                    self.run('activate_build.bat && lib hello.obj -OUT:helloapp.lib')
                    self.run('activate_build.bat && cl /EHsc main.cpp helloapp.lib')
            ''')

        reuse = cpp_hello_conan_files("app", "0.1", deps=["hello2/0.1@user/testing"],
                                      use_cmake=False)
        reuse["conanfile.py"] = reuse_conanfile
        client.save(reuse, clean_first=True)
        client.run("install .")
        client.run("build .")
        client.run_command("main.exe")
        self.assertIn("Hello app;Hello hello2;Hello hello", ";".join(str(client.out).splitlines()))
