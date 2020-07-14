import textwrap
import unittest

import mock

from conans import __version__
from conans.client.tools.version import Version
from conans.test.utils.tools import TestClient


class MinVersionTest(unittest.TestCase):

    def min_version_test(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Lib(ConanFile):
                min_conan_version = "100.0"
            """)
        client.save({"conanfile.py": conanfile})
        client.run("export . pkg/1.0@", assert_error=True)
        self.assertIn("minimum version: 100.0.0 > %s" % __version__, client.out)
        client.run("inspect . ", assert_error=True)
        self.assertIn("minimum version: 100.0.0 > %s" % __version__, client.out)
        with mock.patch("conans.client.loader.current_version", Version("101.0")):
            client.run("export . pkg/1.0@")

        client.run("install pkg/1.0@", assert_error=True)
        self.assertIn("minimum version: 100.0.0 > %s" % __version__, client.out)
