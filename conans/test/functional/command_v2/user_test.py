import contextlib
import io
import unittest

from conans.client.tools import environment_append, six
from conans.test.utils.tools import TestClient
from conans.util.env_reader import get_env


@unittest.skipIf(get_env("TESTING_REVISIONS_ENABLED", False), "Until conan config is implemented")
@unittest.skipIf(six.PY2, "v2.0: Only testing for Python 3")
class CliUserTest(unittest.TestCase):

    def run(self, *args, **kwargs):
        with environment_append({"CONAN_V2_CLI": "1"}):
            super(CliUserTest, self).run(*args, **kwargs)

    def test_user_command(self):
        client = TestClient()

        client.run("user list")
        self.assertIn("remote: remote1 user: someuser1", client.out)
        self.assertIn("remote: remote2 user: someuser2", client.out)
        self.assertIn("remote: remote3 user: someuser3", client.out)
        self.assertIn("remote: remote4 user: someuser4", client.out)
