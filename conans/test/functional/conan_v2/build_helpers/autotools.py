import textwrap
import platform
import unittest

import pytest

from conans.test.utils.conan_v2_tests import ConanV2ModeTestCase


class AutotoolsBuildHelperTestCase(ConanV2ModeTestCase):

    @pytest.mark.skipif(platform.system() != "Linux", reason="Requires make")
    def test_no_build_type(self):
        t = self.get_client()
        conanfile = textwrap.dedent("""
            from conans import ConanFile, AutoToolsBuildEnvironment
            class Pkg(ConanFile):
                settings = "os", "arch", "compiler"
                def build(self):
                  autotools = AutoToolsBuildEnvironment(self)
                  autotools.configure()
                  autotools.make()
        """)
        t.save({"conanfile.py": conanfile})
        t.run("create . pkg/0.1@user/testing", assert_error=True)
        self.assertIn("Conan v2 incompatible: build_type setting should be defined.", t.out)

    @pytest.mark.skipif(platform.system() != "Linux", reason="Requires make")
    def test_no_compiler(self):
        t = self.get_client()
        conanfile = textwrap.dedent("""
            from conans import ConanFile, AutoToolsBuildEnvironment

            class Pkg(ConanFile):
                settings = "os", "arch", "build_type"
                def build(self):
                  autotools = AutoToolsBuildEnvironment(self)
                  autotools.configure()
                  autotools.make()
        """)
        t.save({"conanfile.py": conanfile})
        t.run("create . pkg/0.1@user/testing", assert_error=True)
        self.assertIn("Conan v2 incompatible: compiler setting should be defined.", t.out)
