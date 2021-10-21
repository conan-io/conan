import platform
import textwrap
import unittest

import pytest

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


@pytest.mark.tool_pkg_config
@pytest.mark.tool_mingw32
class PkgConfigTest(unittest.TestCase):
    """
    Test WITHOUT a build helper nor a generator, explicitly defining pkg-config in the
    consumer side
    """
    # FIXME: This test can be removed in Conan 2.0, use only generators and toolchains, this
    # manual usage is not something that Conan tests should be covering

    def test_reuse_pc_approach1(self):

        liba_conanfile = textwrap.dedent("""
            import os
            from conans import ConanFile, tools
            from shutil import copyfile

            class LibAConan(ConanFile):
                settings = "os", "compiler", "build_type", "arch"
                exports_sources = "*.cpp"
                requires = "libB/1.0@conan/stable"

                def build(self):
                    lib_b_path = self.deps_cpp_info["libB"].rootpath
                    copyfile(os.path.join(lib_b_path, "libB.pc"), "libB.pc")
                    # Patch copied file with the libB path
                    tools.replace_prefix_in_pc_file("libB.pc", lib_b_path)

                    with tools.environment_append({"PKG_CONFIG_PATH": os.getcwd()}):
                        # Windows is not able to catch the output, "$()" does not exist in cmd
                        self.run("pkg-config libB --libs --cflags > output.txt")
                        with open("output.txt") as f:
                            self.run('g++ main.cpp %s -o main' % f.readline().strip())
            """)

        self._run_reuse(libb_conanfile, liba_conanfile)

    def test_reuse_pc_approach2(self):

        liba_conanfile = textwrap.dedent("""
            import os
            from conans import ConanFile, tools

            class LibAConan(ConanFile):
                settings = "os", "compiler", "build_type", "arch"
                exports_sources = "*.cpp"
                requires = "libB/1.0@conan/stable"

                def build(self):
                    args = ('--define-variable package_root_path_lib_b=%s'
                            % self.deps_cpp_info["libB"].rootpath)
                    pkgconfig_exec = ('pkg-config --define-variable package_root_path_lib_b=%s'
                                      % (self.deps_cpp_info["libB"].rootpath))
                    vars = {'PKG_CONFIG': pkgconfig_exec, # Used in autotools, not in gcc directly
                            'PKG_CONFIG_PATH': "%s" % self.deps_cpp_info["libB"].rootpath}

                    with tools.environment_append(vars):
                        # Windows is not able to catch the output, "$()" does not exist in cmd
                        self.run("pkg-config %s libB --libs --cflags > output.txt" % args)
                        with open("output.txt") as f:
                            self.run('g++ main.cpp %s -o main' % f.readline().strip())

            """)
        libb = libb_conanfile + """
        path = os.path.join(self.package_folder, "libB.pc")
        tools.replace_prefix_in_pc_file(path, "${package_root_path_lib_b}")
"""
        self._run_reuse(libb, liba_conanfile)

    def _run_reuse(self, conanfile_b, conanfile_a):
        client = TestClient(path_with_spaces=False)  # pc files seems to fail with spaces in paths
        client.save({"conanfile.py": conanfile_b,
                     "hello.cpp": hello_cpp,
                     "hello.h": hello_h}, clean_first=True)
        client.run("create . conan/stable")

        client.save({"conanfile.py": conanfile_a,
                     "main.cpp": main_cpp}, clean_first=True)

        client.run("install .")
        client.run("build .")
        client.run_command("main" if platform.system() == "Windows" else "./main")
        self.assertIn("Hello World!", client.out)
