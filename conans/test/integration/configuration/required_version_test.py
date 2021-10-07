import unittest
import mock

from conans import __version__
from conans.errors import ConanException
from conans.test.utils.tools import TestClient


class RequiredVersionTest(unittest.TestCase):

    @mock.patch("conans.client.conf.required_version.client_version", "1.26.0")
    def test_wrong_version(self):
        required_version = "1.23.0"
        client = TestClient()
        client.run("config set general.required_conan_version={}".format(required_version))
        with self.assertRaises(ConanException) as error:
            client.run("help")
        self.assertIn("Current Conan version (1.26.0) does not satisfy the defined "
                      "one ({})".format(required_version), str(error.exception))

    @mock.patch("conans.client.conf.required_version.client_version", "1.22.0")
    def test_exact_version(self):
        client = TestClient()
        client.run("config set general.required_conan_version=1.22.0")
        client.run("help")
        self.assertNotIn("ERROR", client.out)

    @mock.patch("conans.client.conf.required_version.client_version", "2.1.0")
    def test_lesser_version(self):
        client = TestClient()
        client.run("config set general.required_conan_version=<3")
        client.run("help")
        self.assertNotIn("ERROR", client.out)

    @mock.patch("conans.client.conf.required_version.client_version", "1.0.0")
    def test_greater_version(self):
        client = TestClient()
        client.run("config set general.required_conan_version=>0.1.0")
        client.run("help")
        self.assertNotIn("ERROR", client.out)

    def test_bad_format(self):
        client = TestClient()
        required_version = "1.0.0.0-foobar"
        client.run("config set general.required_conan_version={}".format(required_version))
        with self.assertRaises(ConanException) as error:
            client.run("help", assert_error=True)
        self.assertIn("Current Conan version ({}) does not satisfy the defined one ({})"
                      .format(__version__, required_version), str(error.exception))
