# coding=utf-8

import os
import unittest
import tempfile
import itertools
from parameterized import parameterized

from conans.test.utils.tools import TestClient
from conans.test import CONAN_TEST_FOLDER
from conans.util.files import save
from conans.paths import LINKED_PACKAGE_SENTINEL, CONAN_PACKAGE_LAYOUT_FILE
from conans.model.ref import ConanFileReference


class HeaderOnlyLibTestClient(TestClient):
    header = """
        #include <iostream>

        void hello() {{
            std::cout << "Hello {build_type}!" << std::endl;
            std::cout << " - options.shared: {shared}" << std::endl;
        }}
        """

    conanfile = """
import os
from conans import ConanFile, tools

class Pkg(ConanFile):
    name = "MyLib"
    version = "0.1"

    exports_sources = "*"
    settings = "build_type"

    options = {"shared": [True, False], }
    default_options = {"shared": True, }

    def package(self):
        self.copy("*.hpp", dst="include", src="src/include")

    def package_info(self):
        self.cpp_info.libs = ["MyLib", "otra", ]
        self.cpp_info.defines = ["MyLibDEFINES",]
        self.cpp_info.libdirs = ["MyLib-libdirs", ]
        self.cpp_info.includedirs = ["MyLib-includedirs", "dddd", ]

    """

    conan_package_layout = """
[{namespace}includedirs]
src/include/{{settings.build_type}}/{{options.shared}}
"""

    def __init__(self, use_repo_file, *args, **kwargs):
        super(HeaderOnlyLibTestClient, self).__init__(*args, **kwargs)

        files = {"conanfile.py": self.conanfile,
                 "src/include/Debug/True/hello.hpp": self.header.format(build_type="Debug",
                                                                        shared="True"),
                 "src/include/Debug/False/hello.hpp": self.header.format(build_type="Debug",
                                                                         shared="False"),
                 "src/include/Release/True/hello.hpp": self.header.format(build_type="Release",
                                                                          shared="True"),
                 "src/include/Release/False/hello.hpp": self.header.format(build_type="Release",
                                                                           shared="False"),
                 }

        if use_repo_file:
            files[CONAN_PACKAGE_LAYOUT_FILE] = self.conan_package_layout.format(namespace="")
        else:
            save(self.client_cache.default_editable_path,
                 self.conan_package_layout.format(namespace="MyLib:"))

        self.save(files)

    def make_editable(self, full_reference):
        ref = ConanFileReference.loads(full_reference)
        cache_dir = self.client_cache.conan(ref)
        save(os.path.join(cache_dir, LINKED_PACKAGE_SENTINEL), content=self.current_folder)


class SettingsAndOptionsTest(unittest.TestCase):

    @parameterized.expand(itertools.product(["Debug", "Release", ],  # build_type
                                            [True, False, ],  # shared
                                            [True, False, ]))  # use_repo_file
    def test_settings_options(self, build_type, shared, use_repo_file):
        # We need two clients sharing the same Conan cache
        base_folder = tempfile.mkdtemp(suffix='conans', dir=CONAN_TEST_FOLDER)

        # Editable project
        client_editable = HeaderOnlyLibTestClient(use_repo_file=use_repo_file,
                                                  base_folder=base_folder)
        client_editable.make_editable(full_reference="MyLib/0.1@user/editable")

        # Consumer project
        client = TestClient(base_folder=base_folder)
        conanfile_txt = """
import os
from conans import ConanFile, CMake

class TestConan(ConanFile):
    name = "pkg"
    version = "0.0"

    requires = "MyLib/0.1@user/editable"
    settings = "os", "compiler", "build_type", "arch"
    generators = "cmake"
    exports_sources = "src/*"

    def build(self):
        cmake = CMake(self)
        cmake.configure(source_folder="src")
        cmake.build()

        os.chdir("bin")
        self.run(".%shello" % os.sep)

"""
        cmakelists = """
cmake_minimum_required(VERSION 2.8.12)
project(MyHello CXX)

include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
conan_basic_setup()

add_executable(hello main.cpp)
"""
        main_cpp = """
#include "hello.hpp"

int main() {
    hello();
}
"""

        client.save({"conanfile.py": conanfile_txt,
                     "src/CMakeLists.txt": cmakelists,
                     "src/main.cpp": main_cpp})

        # Build consumer project
        client.run("create . pkg/0.0@user/testing -s build_type={} -o MyLib:shared={}".format(build_type, str(shared)))
        self.assertIn("    MyLib/0.1@user/editable from local cache - Editable", client.out)
        self.assertIn("Hello {}!".format(build_type), client.out)
        self.assertIn(" - options.shared: {}".format(shared), client.out)
