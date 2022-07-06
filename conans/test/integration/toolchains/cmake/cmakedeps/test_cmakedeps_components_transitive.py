import platform
import textwrap


from conans.test.utils.tools import TestClient


def test_cmakedeps_propagate_components():
    client = TestClient()
    top = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import copy

        class TopConan(ConanFile):
            name = "top"
            version = "1.0"
            settings = "os", "compiler", "build_type", "arch"
            exports_sources = "include/*"

            def package(self):
                copy(self, "*.h", os.path.join(self.source_folder, "include"),
                                   os.path.join(self.package_folder, "include"))

            def package_info(self):
                self.cpp_info.components["cmp1"].includedirs = ["include"]
                self.cpp_info.components["cmp2"].includedirs = ["include"]
        """)

    cmp_include = textwrap.dedent("""
        #pragma once
        #include <iostream>
        void {cmpname}(){{ std::cout << "{cmpname}" << std::endl; }};
        """)

    client.save({
        'top/conanfile.py': top,
        'top/include/cmp1.h': cmp_include.format(cmpname="cmp1"),
        'top/include/cmp2.h': cmp_include.format(cmpname="cmp2"),
    })

    client.run("create top")

    middle = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import copy


        class MiddleConan(ConanFile):
            name = "middle"
            version = "1.0"
            requires = "top/1.0"
            settings = "os", "compiler", "build_type", "arch"
            exports_sources = "include/*"

            def package(self):
                copy(self, "*.h", os.path.join(self.source_folder, "include"),
                                   os.path.join(self.package_folder, "include"))

            def package_info(self):
                self.cpp_info.requires = ["top::cmp1"]
        """)

    middle_include = textwrap.dedent("""
        #pragma once
        #include <iostream>
        #include "cmp1.h"
        void middle(){ cmp1(); };
        """)


    client.save({
        'middle/conanfile.py': middle,
        'middle/include/middle.h': middle_include,
    })

    client.run("create middle")

    client.run("install middle/1.0@ -g CMakeDeps")

    assert "top::cmp2" not in client.load("top-release-x86_64-data.cmake")
    assert "top::cmp2" not in client.load("top-Target-release.cmake")
