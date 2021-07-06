import os
import platform
import textwrap
import unittest

import pytest

from conans.model.ref import ConanFileReference
from conans.test.assets.autotools import gen_makefile_am, gen_configure_ac
from conans.test.assets.sources import gen_function_cpp, gen_function_h
from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestClient


class AutoToolsConfigureTest(unittest.TestCase):

    @pytest.mark.skipif(platform.system() != "Linux", reason="Requires Autotools")
    @pytest.mark.tool_autotools()
    def test_autotools_real_install_dirs(self):
        body = gen_function_cpp(name="hello", msg="Hola Mundo!")
        header = gen_function_h(name="hello")
        main = gen_function_cpp(name="main", includes=["hello"], calls=["hello"])
        makefile_am = gen_makefile_am(main="main", main_srcs="main.cpp", lib="libhello.a",
                                      lib_srcs="hello.cpp")
        configure_ac = gen_configure_ac()

        conanfile = textwrap.dedent("""
            from conans import ConanFile, AutoToolsBuildEnvironment

            class TestConan(ConanFile):
                name = "test"
                version = "1.0"
                settings = "os", "compiler", "arch", "build_type"
                exports_sources = "*"

                def build(self):
                    self.run("aclocal")
                    self.run("autoconf")
                    self.run("automake --add-missing --foreign")
                    autotools = AutoToolsBuildEnvironment(self)
                    autotools.configure()
                    autotools.make()
                    autotools.install()

                def package_id(self):
                    # easier to have same package_id for the test
                    self.info.header_only()
            """)
        client = TestClient()
        client.save({"conanfile.py": conanfile,
                     "configure.ac": configure_ac,
                     "Makefile.am": makefile_am,
                     "main.cpp": main,
                     "hello.h": header,
                     "hello.cpp": body})
        client.run("create . danimtb/testing")
        pref = client.get_latest_prev(ConanFileReference.loads("test/1.0@danimtb/testing"),
                                      NO_SETTINGS_PACKAGE_ID)
        pkg_path = client.get_latest_pkg_layout(pref).package()

        [self.assertIn(folder, os.listdir(pkg_path)) for folder in ["lib", "bin"]]

        new_conanfile = conanfile.replace("autotools.configure()",
                                          "autotools.configure(args=['--bindir=${prefix}/superbindir', '--libdir=${prefix}/superlibdir'])")
        client.save({"conanfile.py": new_conanfile})
        client.run("create . danimtb/testing")
        pkg_path = client.get_latest_pkg_layout(pref).package()
        [self.assertIn(folder, os.listdir(pkg_path)) for folder in ["superlibdir", "superbindir"]]
        [self.assertNotIn(folder, os.listdir(pkg_path)) for folder in ["lib", "bin"]]
