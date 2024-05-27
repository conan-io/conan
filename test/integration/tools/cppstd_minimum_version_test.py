import unittest
from parameterized import parameterized
from textwrap import dedent

from conan.test.utils.tools import TestClient


class CppStdMinimumVersionTests(unittest.TestCase):

    CONANFILE = dedent("""
        import os
        from conan import ConanFile
        from conan.tools.build import check_min_cppstd, valid_min_cppstd

        class Fake(ConanFile):
            name = "fake"
            version = "0.1"
            settings = "compiler"

            def validate(self):
                check_min_cppstd(self, "17", False)
                self.output.info("valid standard")
                assert valid_min_cppstd(self, "17", False)
        """)

    PROFILE = dedent("""
        [settings]
        compiler=gcc
        compiler.version=9
        compiler.libcxx=libstdc++
        {}
        """)

    def setUp(self):
        self.client = TestClient()
        self.client.save({"conanfile.py": CppStdMinimumVersionTests.CONANFILE})

    @parameterized.expand(["17", "gnu17"])
    def test_cppstd_from_settings(self, cppstd):
        profile = CppStdMinimumVersionTests.PROFILE.replace("{}", "compiler.cppstd=%s" % cppstd)
        self.client.save({"myprofile":  profile})
        self.client.run("create . --user=user --channel=channel -pr myprofile")
        self.assertIn("valid standard", self.client.out)

    @parameterized.expand(["11", "gnu11"])
    def test_invalid_cppstd_from_settings(self, cppstd):
        profile = CppStdMinimumVersionTests.PROFILE.replace("{}", "compiler.cppstd=%s" % cppstd)
        self.client.save({"myprofile": profile})
        self.client.run("create . --user=user --channel=channel -pr myprofile", assert_error=True)
        self.assertIn("Invalid: Current cppstd (%s) is lower than the required C++ standard (17)."
                      % cppstd, self.client.out)


def test_header_only_check_min_cppstd():
    """
    Check that for a header only package you can check self.info in the validate
    Related to: https://github.com/conan-io/conan/issues/11786
    """
    conanfile = dedent("""
        import os
        from conan import ConanFile
        from conan.tools.build import check_min_cppstd

        class Fake(ConanFile):
            name = "fake"
            version = "0.1"
            settings = "compiler"
            def package_id(self):
                self.info.clear()
            def validate(self):
                check_min_cppstd(self, "11")
        """)
    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run("create . -s compiler.cppstd=14")
    client.run("install --require=fake/0.1@ -s compiler.cppstd=14")
    assert "fake/0.1: Already installed!" in client.out


def test_validate_build_check_min_cppstd():
    """
    Check the case that a package needs certain cppstd to build but can be consumed with a lower
    cppstd or even not cppstd defined at all
    """
    conanfile = dedent("""
        import os
        from conan import ConanFile
        from conan.tools.build import check_min_cppstd

        class Fake(ConanFile):
            name = "fake"
            version = "0.1"
            settings = "compiler"
            def validate_build(self):
                check_min_cppstd(self, "17")
            def validate(self):
                print("validated")
            def build(self):
                print("built")
            def package_id(self):
                del self.info.settings.compiler.cppstd
        """)
    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run("create . -s compiler.cppstd=14", assert_error=True)
    assert "fake/0.1: Cannot build for this configuration: " \
           "Current cppstd (14) is lower than the required C++ standard (17)." in client.out
    client.run("create . -s compiler.cppstd=17")
    client.run("install --require=fake/0.1@")
    assert "fake/0.1: Already installed!" in client.out
    assert "validated" in client.out
