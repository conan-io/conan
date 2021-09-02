import unittest

import pytest

from conans.test.utils.tools import TestClient


class CliUserTest(unittest.TestCase):

    def run(self, *args, **kwargs):
        super(CliUserTest, self).run(*args, **kwargs)

    @pytest.mark.skip(reason="Command 'user' is not implemented yet")
    def test_user_command(self):
        client = TestClient()

        client.run("user list")
        self.assertIn("remote: remote1 user: someuser1", client.out)
        self.assertIn("remote: remote2 user: someuser2", client.out)
        self.assertIn("remote: remote3 user: someuser3", client.out)
        self.assertIn("remote: remote4 user: someuser4", client.out)
