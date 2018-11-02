# coding=utf-8

import os
import unittest
import tempfile

from conans.test.utils.tools import TestClient
from conans.paths.package_layouts.package_user_layout import CONAN_PACKAGE_LAYOUT_FILE
from conans.test import CONAN_TEST_FOLDER
from conans.util.files import save
from conans.paths import LINKED_FOLDER_SENTINEL
from conans.model.ref import ConanFileReference


class HeaderOnlyLibTestClient(TestClient):
    header = """
        #include <iostream>

        void hello() {{
            std::cout << "Hello {word}!" << std::endl;
        }}
        """

    conanfile = """
import os
from conans import ConanFile, tools

class Pkg(ConanFile):
    name = "MyLib"
    version = "0.1"

    exports_sources = "*"

    def package(self):
        self.copy("*.hpp", dst="include", src="src/include")

    def package_info(self):
        self.cpp_info.libs = ["MyLib", "otra", ]
        self.cpp_info.defines = ["MyLibDEFINES",]
        self.cpp_info.libdirs = ["MyLib-libdirs", ]
        self.cpp_info.includedirs = ["MyLib-includedirs", "include", ]

    """

    conan_package_layout = """
[includedirs]
src/include
"""

    def __init__(self, *args, **kwargs):
        super(HeaderOnlyLibTestClient, self).__init__(*args, **kwargs)
        self.save({"conanfile.py": self.conanfile,
                   CONAN_PACKAGE_LAYOUT_FILE: self.conan_package_layout,
                   "src/include/hello.hpp": self.header.format(word="EDITABLE")})

    def update_hello_word(self, hello_word):
        self.save({"src/include/hello.hpp": self.header.format(word=hello_word)})

    def make_editable(self, full_reference):
        conan_ref = ConanFileReference.loads(full_reference)
        cache_dir = self.client_cache.conan(conan_ref)
        save(os.path.join(cache_dir, LINKED_FOLDER_SENTINEL), content=self.current_folder)


class EditableReferenceTest(unittest.TestCase):

    def test_header_only(self):
        # We need two clients sharing the same Conan cache
        base_folder = tempfile.mkdtemp(suffix='conans', dir=CONAN_TEST_FOLDER)

        # Editable project
        client_editable = HeaderOnlyLibTestClient(base_folder=base_folder)
        client_editable.make_editable(full_reference="MyLib/0.1@user/editable")
        # client_editable.run("editable . MyLib/0.1@user/editable")  # 'Install' as editable

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

        """
        client.run("install . -g txt -g cmake")

        text = load(os.path.join(client.current_folder, "conanbuildinfo.txt"))
        #txt = ";".join(text.splitlines())
        #self.assertNotIn("[libs];MyLib", txt)
        cmake = load(os.path.join(client.current_folder, "conanbuildinfo.cmake"))
        #self.assertIn("set(CONAN_LIBS MyLib ${CONAN_LIBS})", cmake)
        """

        # Build consumer project
        client.run("create . pkg/0.0@user/testing")
        self.assertIn("Hello EDITABLE!", client.out)

        # Modify editable and build again
        client_editable.update_hello_word(hello_word="EDITED")
        client.run("create . pkg/0.0@user/testing")
        self.assertIn("Hello EDITED!", client.out)
