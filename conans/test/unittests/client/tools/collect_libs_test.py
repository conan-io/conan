import platform
import textwrap
import unittest

import pytest

from conans.test.utils.tools import TestClient, GenConanfile


class CollectLibsTest(unittest.TestCase):

    @pytest.mark.xfail(reason="cache2.0")
    def test_collect_libs(self):
        conanfile = textwrap.dedent("""
            import os
            from conan import ConanFile
            from conan.tools.files import copy
            class Pkg(ConanFile):
                exports_sources = "*"
                def package(self):
                    copy(self, "*", self.source_folder, dst=os.path.join(self.package_folder, "lib"))
                def package_info(self):
                    from conans import tools
                    self.cpp_info.libs = tools.collect_libs(self)
            """)
        client = TestClient()
        lib_name = "mylibname.%s" % ("a" if platform.system() != "Windows" else "lib")
        client.save({"conanfile.py": conanfile,
                     lib_name: ""})
        client.run("create . --name=mylib --version=0.1 --user=user --channel=channel")

        # reusing the binary already in cache
        client.save({"conanfile.py": GenConanfile().with_require("mylib/0.1@user/channel")
                     .with_settings("build_type")},
                    clean_first=True)
        client.run('install . -g CMakeDeps')
        conanbuildinfo = client.load("mylib-release-data.cmake")
        self.assertIn("set(mylib_LIBS_RELEASE mylibname)", conanbuildinfo)

        # rebuilding the binary in cache
        client.run('remove "*" -p -c')
        client.run('install . --build -g cmake')
        conanbuildinfo = client.load("mylib-release-data.cmake")
        self.assertIn("set(mylib_LIBS_RELEASE mylibname)", conanbuildinfo)
