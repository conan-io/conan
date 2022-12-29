import os
import unittest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


class UserChannelTestPackage(unittest.TestCase):

    def test(self):
        # https://github.com/conan-io/conan/issues/2501
        client = TestClient()
        conanfile = """from conans import ConanFile
class SayConan(ConanFile):
    pass
"""
        test = """from conans import ConanFile
class SayConan(ConanFile):
    def requirements(self):
        self.output.info("USER: %s!!" % self.user)
        self.output.info("CHANNEL: %s!!" % self.channel)

    def test(self):
        pass
"""

        client.save({"conanfile.py": conanfile,
                     "test_package/conanfile.py": test})
        client.run("create . Pkg/0.1@conan/testing")
        self.assertIn("Pkg/0.1@conan/testing (test package): USER: conan!!", client.out)
        self.assertIn("Pkg/0.1@conan/testing (test package): CHANNEL: testing!!", client.out)


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

        self.test_conanfile = str(GenConanfile().with_require("Hello/0.1@lasote/stable")
                                                .with_test("pass"))
        self.client.save({"conanfile.py": self.conanfile,
                          "test/conanfile.py": self.test_conanfile})

    def test_create(self):
        self.client.run("create . lasote/stable")
        self.assertIn("Say/0.1@lasote/stable: Building lasote/stable", self.client.out)
        self.assertIn("Hello/0.1@lasote/stable: Building lasote/stable", self.client.out)
        self.assertNotIn("other/testing", self.client.out)

        self.client.save({"conanfile.py": self.conanfile,
                          "test/conanfile.py": self.test_conanfile.replace("lasote/stable",
                                                                           "other/testing")})
        self.client.run("create . other/testing")
        self.assertIn("Say/0.1@other/testing: Building other/testing", self.client.out)
        self.assertIn("Hello/0.1@other/testing: Building other/testing", self.client.out)
        self.assertNotIn("lasote/stable", self.client.out)

    def test_local_commands(self):
        self.client.run("install .", assert_error=True)
        self.assertIn("ERROR: conanfile.py (Hello/0.1): "
                      "Error in requirements() method, line 10", self.client.out)
        self.assertIn("ConanException: user not defined, but self.user is used in"
                      " conanfile", self.client.out)

        os.environ["CONAN_USERNAME"] = "lasote"
        self.client.run("install .", assert_error=True)
        self.assertIn("ERROR: conanfile.py (Hello/0.1): "
                      "Error in requirements() method, line 10", self.client.out)
        self.assertIn("ConanException: channel not defined, but self.channel is used in"
                      " conanfile", self.client.out)

        os.environ["CONAN_CHANNEL"] = "stable"
        self.client.run("install .")
        self.assertIn("Say/0.1@lasote/stable: Building lasote/stable", self.client.out)
        self.assertNotIn("other/testing", self.client.out)

        os.environ["CONAN_USERNAME"] = "other"
        os.environ["CONAN_CHANNEL"] = "testing"
        self.client.run("install .")
        self.assertIn("Say/0.1@other/testing: Building other/testing", self.client.out)
        self.assertNotIn("lasote/stable", self.client.out)

        del os.environ["CONAN_USERNAME"]
        del os.environ["CONAN_CHANNEL"]

        # Now use the default_ methods to declare user and channel
        self.client = TestClient()
        conanfile = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.1"
    build_policy = "missing"
    default_user = "userfoo"

    def build(self):
        self.output.info("Building %s/%s" % (self.user, self.channel) )

    @property
    def default_channel(self):
        return "channelbar"
"""
        self.client.save({"conanfile.py": conanfile})
        self.client.run("install .")
        self.client.run("build .")
        self.assertIn("Building userfoo/channelbar", self.client.out)


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
