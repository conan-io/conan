import os
import platform
import unittest

from conans.paths import CONANFILE
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.test.utils.tools import TestClient
from conans.util.files import mkdir


class PkgConfigGeneratorTest(unittest.TestCase):

    def test_base(self):

        client = TestClient(path_with_spaces=False)
        self._export(client, "LIB_C", [])
        self._export(client, "LIB_B", ["LIB_C"])
        self._export(client, "LIB_B2", [])
        self._export(client, "LIB_A", ["LIB_B", "LIB_B2"])

        consumer = """
from conans import ConanFile, tools, Meson
import os

class ConanFileToolsTest(ConanFile):
    generators = "pkg_config"
    requires = "LIB_A/0.1@conan/stable"
    settings = "os", "compiler", "build_type"

    def build(self):
        meson = Meson(self)
        meson.configure()
        meson.build()
        
"""
        meson_build = """
project('conan_hello', 'c')
liba = dependency('LIB_A', version : '>=0')
executable('demo', 'main.c', dependencies: [liba])
"""

        main_c = """
#include "helloLIB_A.h"

int main(){
  helloLIB_A();
}
"""

        client.save({CONANFILE: consumer,
                     "meson.build": meson_build,
                     "main.c": main_c}, clean_first=True)
        mkdir(os.path.join(client.current_folder, "build"))
        client.current_folder = os.path.join(client.current_folder, "build")
        client.run("install .. --build")
        client.run("build .. --source_folder ..")
        if platform.system() == "Windows":
            command = "demo"
        else:
            command = './demo'
        client.runner(command, cwd=os.path.join(client.current_folder))
        self.assertEqual(['Hello LIB_A', 'Hello LIB_B', 'Hello LIB_C', 'Hello LIB_B2'],
                         str(client.user_io.out).splitlines()[-4:])

    def _export(self, client, libname, depsname):
        files = cpp_hello_conan_files(libname, "0.1",
                                      ["%s/0.1@conan/stable" % name for name in depsname],
                                      build=True, pure_c=True)
        client.save(files, clean_first=True)
        files[CONANFILE] = files[CONANFILE].replace('generators = "cmake", "gcc"', "")
        client.run("export conan/stable")
