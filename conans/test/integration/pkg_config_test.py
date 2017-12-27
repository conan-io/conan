import platform
import unittest

import subprocess

from conans.test.utils.tools import TestClient

hello_cpp = """
#include <iostream>
#include "hello.h"
void hello(){
    std::cout << "Hello World!";
}
"""

hello_h = """
#pragma once
void hello();
"""

main_cpp = """
#include "hello.h"

int main() {
    hello();
    return 0;
}
"""



class PkgConfigTest(unittest.TestCase):

    def test_reuse_pc_approach1(self):

        libb_conanfile = """
import os
from conans import ConanFile, tools

class LibBConan(ConanFile):
    name = "libB"
    version = "1.0"
    settings = "os", "compiler", "build_type", "arch"
    exports_sources = "*.cpp", "*.h"

    def build(self):
        self.run("g++ -c -o out.o hello.cpp")
        self.run("ar rcs libB.a out.o")

    def package(self):
        self.copy("*.h", dst="include")
        self.copy("*.a", dst="lib", keep_path=False)

    def package_info(self):
        pc_file = '''
prefix=/crazy/path/to/nowhere
exec_prefix=${prefix}
libdir=${exec_prefix}/lib
sharedlibdir=${libdir}
includedir=${prefix}/include

Name: libB
Description: libB library
Version: 1.0

Requires:
Libs: -L${libdir} -L${sharedlibdir} -lB
Cflags: -I${includedir}
'''
        tools.save(os.path.join(self.package_folder, "libB.pc"), pc_file)

"""

        liba_conanfile = """
import os
from conans import ConanFile, tools
from shutil import copyfile

class LibAConan(ConanFile):
    name = "libA"
    version = "1.0"
    settings = "os", "compiler", "build_type", "arch"
    exports_sources = "*.cpp"
    requires = "libB/1.0@conan/stable"

    def build(self):
        lib_b_path = self.deps_cpp_info["libB"].rootpath
        copyfile(os.path.join(lib_b_path, "libB.pc"), "libB.pc")
        # Patch copied file with the libB path
        tools.replace_prefix_in_pc_file("libB.pc", lib_b_path)

        with tools.environment_append({"PKG_CONFIG_PATH": os.getcwd()}):
           self.run('g++ main.cpp $(pkg-config libB --libs --cflags) -o main')

"""

        if platform.system() == "Windows":
            return

        self._run_reuse(libb_conanfile, liba_conanfile)

    def test_reuse_pc_approach2(self):
        libb_conanfile = """
import os
from conans import ConanFile, tools

class LibBConan(ConanFile):
    name = "libB"
    version = "1.0"
    settings = "os", "compiler", "build_type", "arch"
    exports_sources = "*.cpp", "*.h"

    def build(self):
        self.run("g++ -c -o out.o hello.cpp")
        self.run("ar rcs libB.a out.o")

    def package(self):
        self.copy("*.h", dst="include")
        self.copy("*.a", dst="lib", keep_path=False)

    def package_info(self):
        pc_file = '''
prefix=/crazy/path/to/nowhere
exec_prefix=${prefix}
libdir=${exec_prefix}/lib
sharedlibdir=${libdir}
includedir=${prefix}/include

Name: libB
Description: libB library
Version: 1.0

Requires:
Libs: -L${libdir} -L${sharedlibdir} -lB
Cflags: -I${includedir}
'''
        path = os.path.join(self.package_folder, "libB.pc")
        tools.save(path, pc_file)
        tools.replace_prefix_in_pc_file(path, "${package_root_path_lib_b}")

"""

        liba_conanfile = """
import os
from conans import ConanFile, tools

class LibAConan(ConanFile):
    name = "libA"
    version = "1.0"
    settings = "os", "compiler", "build_type", "arch"
    exports_sources = "*.cpp"
    requires = "libB/1.0@conan/stable"

    def build(self):

        args = '--define-variable package_root_path_lib_b=%s' % self.deps_cpp_info["libB"].rootpath
        pkgconfig_exec = 'pkg-config --define-variable package_root_path_lib_b=%s' % (self.deps_cpp_info["libB"].rootpath)
        vars = {'PKG_CONFIG': pkgconfig_exec, # Used in autotools, not in gcc directly
                'PKG_CONFIG_PATH': "%s" % self.deps_cpp_info["libB"].rootpath}

        with tools.environment_append(vars):
           self.run('g++ main.cpp $(pkg-config %s libB --libs --cflags) -o main' % args)

"""

        if platform.system() == "Windows":
            return

        self._run_reuse(libb_conanfile, liba_conanfile)

    def _run_reuse(self, conanfile_b, conanfile_a):
        client = TestClient(path_with_spaces=False)  # pc files seems to fail with spaces in paths
        client.save({"conanfile.py": conanfile_b,
                     "hello.cpp": hello_cpp,
                     "hello.h": hello_h}, clean_first=True)
        client.run("export . conan/stable")
        client.run("install libB/1.0@conan/stable --build missing")

        client.save({"conanfile.py": conanfile_a,
                     "main.cpp": main_cpp}, clean_first=True)

        client.run("install .")
        client.run("build .")

        subprocess.Popen("./main", cwd=client.current_folder)
