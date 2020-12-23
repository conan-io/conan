# coding=utf-8

import itertools
import os
import unittest

import pytest
from parameterized import parameterized

from conans.model.editable_layout import DEFAULT_LAYOUT_FILE, LAYOUTS_FOLDER
from conans.test.utils.tools import TestClient
from conans.util.files import save
from conans.test.utils.test_files import temp_folder


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
[%sincludedirs]
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
            files["mylayout"] = self.conan_package_layout % ""
        else:
            file_path = os.path.join(self.cache.cache_folder, LAYOUTS_FOLDER, DEFAULT_LAYOUT_FILE)
            save(file_path,
                 self.conan_package_layout % "MyLib/0.1@user/editable:")

        self.save(files)


@pytest.mark.tool_cmake
class SettingsAndOptionsTest(unittest.TestCase):

    @parameterized.expand(itertools.product(["Debug", "Release", ],  # build_type
                                            [True, False, ],  # shared
                                            [True, False, ]))  # use_repo_file
    def test_settings_options(self, build_type, shared, use_repo_file):
        # We need two clients sharing the same Conan cache
        cache_folder = temp_folder()

        # Editable project
        client_editable = HeaderOnlyLibTestClient(use_repo_file=use_repo_file,
                                                  cache_folder=cache_folder)
        if use_repo_file:
            client_editable.run("editable add . MyLib/0.1@user/editable -l=mylayout")
        else:
            client_editable.run("editable add . MyLib/0.1@user/editable")

        # Consumer project
        client = TestClient(cache_folder=cache_folder)
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
        client.run("create . pkg/0.0@user/testing "
                   "-s build_type={} -o MyLib:shared={}".format(build_type, str(shared)))
        self.assertIn("    MyLib/0.1@user/editable from user folder - Editable", client.out)
        self.assertIn("Hello {}!".format(build_type), client.out)
        self.assertIn(" - options.shared: {}".format(shared), client.out)
