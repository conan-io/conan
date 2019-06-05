# coding=utf-8

import textwrap
import unittest

from conans.test.utils.tools import TestClient


class OptionsWithTestPackage(unittest.TestCase):
    binutils = textwrap.dedent(r"""
        from conans import ConanFile
        
        class Binutils(ConanFile):
            name = "binutils"
            version = "0.1"
            
            options = {"target": "ANY"}
            default_options = {"target": None}
    """)

    gcc = textwrap.dedent(r"""
        from conans import ConanFile

        class Gcc(ConanFile):
            name = "gcc"
            version = "0.1"

            def build_requirements(self):
                self.build_requires("binutils/0.1@user/channel", context='build')
    """)

    test_package = textwrap.dedent(r"""
        from conans import ConanFile
        
        class TestPackage(ConanFile):
            pass
    """)

    def test_option_cli(self):
        self.t = TestClient()
        self.t.save({'binutils.py': self.binutils,
                     'gcc.py': self.gcc,
                     'test_package/conanfile.py': self.test_package
                     })
        self.t.run("export binutils.py user/channel")
        self.t.run("create gcc.py user/channel -o:b binutils:target=arm", assert_error=True)

        # It should look for (and fail) a binutils package with option.target=arm
        self.assertIn("- Options: target=arm", self.t.out)
