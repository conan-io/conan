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
            self.client.run("export . %s" % channel)

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
        pass
"""
        self.client.save({"conanfile.py": self.conanfile,
                          "test/conanfile.py": self.test_conanfile})

    def test_create(self):
        self.client.run("create . lasote/stable")
        self.assertIn("Say/0.1@lasote/stable: Building lasote/stable", self.client.user_io.out)
        self.assertIn("Hello/0.1@lasote/stable: Building lasote/stable", self.client.user_io.out)
        self.assertNotIn("other/testing", self.client.user_io.out)

        self.client.save({"conanfile.py": self.conanfile,
                          "test/conanfile.py": self.test_conanfile.replace("lasote/stable",
                                                                           "other/testing")})
        self.client.run("create . other/testing")
        self.assertIn("Say/0.1@other/testing: Building other/testing", self.client.user_io.out)
        self.assertIn("Hello/0.1@other/testing: Building other/testing", self.client.user_io.out)
        self.assertNotIn("lasote/stable", self.client.user_io.out)

    def test_local_commands(self):
        error = self.client.run("install .", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: Hello/0.1@PROJECT: Error in requirements() method, line 10", self.client.out)
        self.assertIn("ConanException: CONAN_USERNAME environment variable not defined, but self.user is used",
                      self.client.out)

        os.environ["CONAN_USERNAME"] = "lasote"
        error = self.client.run("install .", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: Hello/0.1@PROJECT: Error in requirements() method, line 10", self.client.out)
        self.assertIn("ConanException: CONAN_CHANNEL environment variable not defined, but self.channel is used",
                      self.client.out)

        os.environ["CONAN_CHANNEL"] = "stable"
        self.client.run("install .")
        self.assertIn("Say/0.1@lasote/stable: Building lasote/stable", self.client.user_io.out)
        self.assertNotIn("other/testing", self.client.user_io.out)

        os.environ["CONAN_USERNAME"] = "other"
        os.environ["CONAN_CHANNEL"] = "testing"
        self.client.run("install .")
        self.assertIn("Say/0.1@other/testing: Building other/testing", self.client.user_io.out)
        self.assertNotIn("lasote/stable", self.client.user_io.out)

        del os.environ["CONAN_USERNAME"]
        del os.environ["CONAN_CHANNEL"]


class BuildRequireUserChannelTest(unittest.TestCase):
    def test(self):
        # https://github.com/conan-io/conan/issues/2254
        client = TestClient()
        conanfile = """
from conans import ConanFile

class SayConan(ConanFile):
    def build_requirements(self):
        self.output.info("MYUSER: %s" % self.user)
        self.output.info("MYCHANNEL: %s" % self.channel)
"""
        client.save({"conanfile.py": conanfile})
        client.run("install . -e CONAN_USERNAME=myuser -e CONAN_CHANNEL=mychannel")
        self.assertIn("MYUSER: myuser", client.out)
        self.assertIn("MYCHANNEL: mychannel", client.out)

    def test_profile(self):
        # https://github.com/conan-io/conan/issues/2254
        client = TestClient()
        conanfile = """
from conans import ConanFile

class SayConan(ConanFile):
    def build_requirements(self):
        self.output.info("MYUSER: %s" % self.user)
        self.output.info("MYCHANNEL: %s" % self.channel)
"""
        myprofile = """[env]
CONAN_USERNAME=myuser
CONAN_CHANNEL=mychannel
"""
        client.save({"conanfile.py": conanfile,
                     "myprofile": myprofile})
        client.run("install . -pr=myprofile")
        self.assertIn("MYUSER: myuser", client.out)
        self.assertIn("MYCHANNEL: mychannel", client.out)
