# coding=utf-8

import os
import tempfile
import unittest
import textwrap

from parameterized import parameterized

from conans.model.ref import ConanFileReference
from conans.paths import LINKED_PACKAGE_SENTINEL, CONAN_PACKAGE_LAYOUT_FILE
from conans.test import CONAN_TEST_FOLDER
from conans.test.utils.tools import TestClient
from conans.util.files import save


class HeaderOnlyLibTestClient(TestClient):
    header = textwrap.dedent("""\
        #include <iostream>

        void hello() {{
            std::cout << "Hello {word}!" << std::endl;
            std::cout << "...using {origin}" << std::endl;
        }}
        """)

    conanfile = textwrap.dedent("""\
        import os
        from conans import ConanFile, tools
        
        class Pkg(ConanFile):
            name = "MyLib"
            version = "0.1"
        
            exports_sources = "*"
        
            def package(self):
                self.copy("*.hpp", dst="include-inrepo", src="src/include-inrepo")
                self.copy("*.hpp", dst="include-cache", src="src/include-cache")
        
            def package_info(self):
                self.cpp_info.libs = ["MyLib", "otra", ]
                self.cpp_info.defines = ["MyLibDEFINES",]
                self.cpp_info.libdirs = ["MyLib-libdirs", ]
                self.cpp_info.includedirs = ["src/include-local", ]
        """)

    conan_inrepo_layout = textwrap.dedent("""\
        [includedirs]
        src/include-inrepo
        """)

    conan_cache_layout = textwrap.dedent("""\
        [MyLib:includedirs]
        src/include-cache
        """)

    def __init__(self, use_repo_file, use_cache_file, *args, **kwargs):
        super(HeaderOnlyLibTestClient, self).__init__(*args, **kwargs)

        self.save({"conanfile.py": self.conanfile,
                   "src/include-inrepo/hello.hpp": self.header.format(word="EDITABLE",
                                                                      origin="inrepo"),
                   "src/include-cache/hello.hpp": self.header.format(word="EDITABLE",
                                                                     origin="cache"),
                   "src/include-local/hello.hpp": self.header.format(word="EDITABLE",
                                                                     origin="local")
                   })

        if use_repo_file:
            self.save({CONAN_PACKAGE_LAYOUT_FILE: self.conan_inrepo_layout, })

        if use_cache_file:
            save(self.client_cache.default_editable_path, self.conan_cache_layout)

    def update_hello_word(self, hello_word):
        self.save({"src/include-inrepo/hello.hpp": self.header.format(word=hello_word,
                                                                      origin='inrepo'),
                   "src/include-cache/hello.hpp": self.header.format(word=hello_word,
                                                                     origin='cache'),
                   "src/include-local/hello.hpp": self.header.format(word=hello_word,
                                                                     origin='local')})

    def make_editable(self, full_reference):
        ref = ConanFileReference.loads(full_reference)
        cache_dir = self.client_cache.conan(ref)
        save(os.path.join(cache_dir, LINKED_PACKAGE_SENTINEL), content=self.current_folder)


class EditableReferenceTest(unittest.TestCase):

    @parameterized.expand([(False, True), (True, False), (True, True), (False, False)])
    def test_header_only(self, use_repo_file, use_cache_file):
        # We need two clients sharing the same Conan cache
        base_folder = tempfile.mkdtemp(suffix='conans', dir=CONAN_TEST_FOLDER)

        # Editable project
        client_editable = HeaderOnlyLibTestClient(use_repo_file=use_repo_file,
                                                  use_cache_file=use_cache_file,
                                                  base_folder=base_folder)
        client_editable.make_editable(full_reference="MyLib/0.1@user/editable")

        # Consumer project
        client = TestClient(base_folder=base_folder)
        conanfile_py = """
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

        client.save({"conanfile.py": conanfile_py,
                     "src/CMakeLists.txt": cmakelists,
                     "src/main.cpp": main_cpp})

        # Build consumer project
        client.run("create . pkg/0.0@user/testing")
        self.assertIn("    MyLib/0.1@user/editable from local cache - Editable", client.out)
        self.assertIn("    MyLib/0.1@user/editable:"
                      "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Editable", client.out)
        self.assertIn("Hello EDITABLE!", client.out)
        if use_repo_file:  # Repo file will override folders from cache
            self.assertIn("...using inrepo", client.out)
            self.assertNotIn("...using cache", client.out)
            self.assertNotIn("...using local", client.out)
        elif use_cache_file:
            self.assertIn("...using cache", client.out)
            self.assertNotIn("...using inrepo", client.out)
            self.assertNotIn("...using local", client.out)
        else:
            self.assertIn("...using local", client.out)
            self.assertNotIn("...using inrepo", client.out)
            self.assertNotIn("...using cache", client.out)

        # Modify editable and build again
        client_editable.update_hello_word(hello_word="EDITED")
        client.run("create . pkg/0.0@user/testing")
        self.assertIn("Hello EDITED!", client.out)
        if use_repo_file:  # Repo file will override folders from cache
            self.assertIn("...using inrepo", client.out)
            self.assertNotIn("...using cache", client.out)
            self.assertNotIn("...using local", client.out)
        elif use_cache_file:
            self.assertIn("...using cache", client.out)
            self.assertNotIn("...using inrepo", client.out)
            self.assertNotIn("...using local", client.out)
        else:
            self.assertIn("...using local", client.out)
            self.assertNotIn("...using inrepo", client.out)
            self.assertNotIn("...using cache", client.out)
