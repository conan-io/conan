import os
import platform
import textwrap
import unittest

import pytest

from conans.client import tools
from conans.model.ref import ConanFileReference, PackageReference
from conans.paths import CONANFILE
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
        pref = PackageReference.loads("test/1.0@danimtb/testing:%s" % NO_SETTINGS_PACKAGE_ID)
        pkg_path = client.cache.package_layout(pref.ref).package(pref)

        [self.assertIn(folder, os.listdir(pkg_path)) for folder in ["lib", "bin"]]

        new_conanfile = conanfile.replace("autotools.configure()",
                                          "autotools.configure(args=['--bindir=${prefix}/superbindir', '--libdir=${prefix}/superlibdir'])")
        client.save({"conanfile.py": new_conanfile})
        client.run("create . danimtb/testing")
        [self.assertIn(folder, os.listdir(pkg_path)) for folder in ["superlibdir", "superbindir"]]
        [self.assertNotIn(folder, os.listdir(pkg_path)) for folder in ["lib", "bin"]]

    @pytest.mark.skipif(platform.system() == "Windows", reason="Not in Windows")
    def test_pkg_config_paths(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile, tools, AutoToolsBuildEnvironment

            class HelloConan(ConanFile):
                name = "Hello"
                version = "1.2.1"
                generators = %s

                def build(self):
                    tools.save("configure", "printenv")
                    self.run("chmod +x configure")
                    autot = AutoToolsBuildEnvironment(self)
                    autot.configure(%s)
            """)

        client.save({CONANFILE: conanfile % ("'txt'", "")})
        client.run("create . conan/testing")
        self.assertNotIn("PKG_CONFIG_PATH=", client.out)

        ref = ConanFileReference.loads("Hello/1.2.1@conan/testing")
        builds_folder = client.cache.package_layout(ref).builds()
        bf = os.path.join(builds_folder, os.listdir(builds_folder)[0])

        client.save({CONANFILE: conanfile % ("'pkg_config'", "")})
        client.run("create . conan/testing")
        self.assertIn("PKG_CONFIG_PATH=%s" % bf, client.out)

        # The previous values in the environment should be kept too
        with tools.environment_append({"PKG_CONFIG_PATH": "Some/value"}):
            client.run("create . conan/testing")
            self.assertIn("PKG_CONFIG_PATH=%s:Some/value" % bf, client.out)

        client.save({CONANFILE: conanfile % ("'pkg_config'",
                                             "pkg_config_paths=['/tmp/hello', 'foo']")})
        client.run("create . conan/testing")
        self.assertIn("PKG_CONFIG_PATH=/tmp/hello:%s/foo" % bf, client.out)

        # The previous values in the environment should be kept too
        with tools.environment_append({"PKG_CONFIG_PATH": "Some/value"}):
            client.run("create . conan/testing")
            self.assertIn("PKG_CONFIG_PATH=/tmp/hello:%s/foo:Some/value" % bf, client.out)
