import unittest
from conans.test.utils.tools import TestClient
from conans import __version__ as client_version


class RequiredVersionTest(unittest.TestCase):

    def setUp(self):
        self.client = TestClient()

    def test_wrong_version(self):
        # include_prerelease is required due the suffix -dev
        required_version = ">=10.0.0,include_prerelease=True"
        self.client.run("config set general.required_conan_version={}".format(required_version))
        self.client.run("help")
        self.assertIn("WARN: The current Conan version ({}) "
                      "does not match to the required version ({})."
                      .format(client_version, required_version), self.client.out)

    def test_exact_version(self):
        self.client.run("config set general.required_conan_version={}".format(client_version))
        self.client.run("help")
        self.assertNotIn("WARN", self.client.out)

    def test_lesser_version(self):
        self.client.run("config set general.required_conan_version=<3,include_prerelease=True")
        self.client.run("help")
        self.assertNotIn("WARN", self.client.out)

    def test_greater_version(self):
        self.client.run("config set general.required_conan_version=>0.1.0,include_prerelease=True")
        self.client.run("help")
        self.assertNotIn("WARN", self.client.out)

    def test_bad_format(self):
        required_version = "1.0.0.0-foobar"
        self.client.run("config set general.required_conan_version={}".format(required_version))
        self.client.run("help", assert_error=True)
        self.assertIn("ERROR: version range expression '1.0.0.0-foobar' is not valid",
                      self.client.out)
