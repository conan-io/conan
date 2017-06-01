import unittest
from conans.test.utils.tools import TestClient
import os


class SameUserChannelTest(unittest.TestCase):

    def setUp(self):
        self.client = TestClient()
        conanfile = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.1"
    build_policy = "missing"

    def build(self):
        self.output.info("Building %s")
"""
        for channel in ("lasote/stable", "other/testing"):
            self.client.save({"conanfile.py": conanfile % channel})
            self.client.run("export %s" % channel)

        self.conanfile = """
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"
    build_policy = "missing"

    def requirements(self):
        self.requires("Say/0.1@%s/%s" % (self.user, self.channel))

    def build(self):
        self.output.info("Building %s/%s" % (self.user, self.channel) )
"""

        self.test_conanfile = """
from conans import ConanFile, CMake
import os

class HelloReuseConan(ConanFile):
    requires = "Hello/0.1@lasote/stable"

    def test(self):
        self.conanfile_directory
"""
        self.client.save({"conanfile.py": self.conanfile,
                          "test/conanfile.py": self.test_conanfile})

    def test_testpackage(self):
        self.client.run("test_package")
        self.assertIn("Say/0.1@lasote/stable: Building lasote/stable", self.client.user_io.out)
        self.assertIn("Hello/0.1@lasote/stable: Building lasote/stable", self.client.user_io.out)
        self.assertNotIn("other/testing", self.client.user_io.out)

        self.client.save({"conanfile.py": self.conanfile,
                          "test/conanfile.py": self.test_conanfile.replace("lasote/stable",
                                                                           "other/testing")})
        self.client.run("test_package")
        self.assertIn("Say/0.1@other/testing: Building other/testing", self.client.user_io.out)
        self.assertIn("Hello/0.1@other/testing: Building other/testing", self.client.user_io.out)
        self.assertNotIn("lasote/stable", self.client.user_io.out)

    def test_local_commands(self):
        error = self.client.run("install", ignore_error=True)
        self.assertEqual(error, True)
        self.assertIn('''ERROR: Hello/0.1@PROJECT: Error in requirements() method, line 10
	self.requires("Say/0.1@%s/%s" % (self.user, self.channel))
	ConanException: CONAN_USERNAME environment variable not defined, but self.user is used in conanfile''', self.client.user_io.out)

        os.environ["CONAN_USERNAME"] = "lasote"
        error = self.client.run("install", ignore_error=True)
        self.assertEqual(error, True)
        self.assertIn("""ERROR: Hello/0.1@PROJECT: Error in requirements() method, line 10
	self.requires("Say/0.1@%s/%s" % (self.user, self.channel))
	ConanException: CONAN_CHANNEL environment variable not defined, but self.channel is used in conanfile""", self.client.user_io.out)

        os.environ["CONAN_CHANNEL"] = "stable"
        self.client.run("install")
        self.assertIn("Say/0.1@lasote/stable: Building lasote/stable", self.client.user_io.out)
        self.assertNotIn("other/testing", self.client.user_io.out)

        os.environ["CONAN_USERNAME"] = "other"
        os.environ["CONAN_CHANNEL"] = "testing"
        self.client.run("install")
        self.assertIn("Say/0.1@other/testing: Building other/testing", self.client.user_io.out)
        self.assertNotIn("lasote/stable", self.client.user_io.out)

        del os.environ["CONAN_USERNAME"]
        del os.environ["CONAN_CHANNEL"]
