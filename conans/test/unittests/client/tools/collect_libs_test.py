import platform
import textwrap
import unittest

from conans.test.utils.tools import TestClient, GenConanfile


class CollectLibsTest(unittest.TestCase):

    def test_collect_libs(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                exports_sources = "*"
                def package(self):
                    self.copy("*", dst="lib")
                def package_info(self):
                    from conans import tools
                    self.cpp_info.libs = tools.collect_libs(self)
            """)
        client = TestClient()
        lib_name = "mylibname.%s" % ("a" if platform.system() != "Windows" else "lib")
        client.save({"conanfile.py": conanfile,
                     lib_name: ""})
        client.run("create . mylib/0.1@user/channel")

        # reusing the binary already in cache
        client.save({"conanfile.py": GenConanfile().with_require("mylib/0.1@user/channel")},
                    clean_first=True)
        client.run('install . -g cmake')
        conanbuildinfo = client.load("conanbuildinfo.cmake")
        self.assertIn("set(CONAN_LIBS_MYLIB mylibname)", conanbuildinfo)
        self.assertIn("set(CONAN_LIBS mylibname ${CONAN_LIBS})", conanbuildinfo)

        # rebuilding the binary in cache
        client.run('remove "*" -p -f')
        client.run('install . --build -g cmake')
        conanbuildinfo = client.load("conanbuildinfo.cmake")
        self.assertIn("set(CONAN_LIBS_MYLIB mylibname)", conanbuildinfo)
        self.assertIn("set(CONAN_LIBS mylibname ${CONAN_LIBS})", conanbuildinfo)
