import unittest

import pytest

from conans.client.tools import environment_append, six
from conans.test.utils.tools import TestClient
from conans.util.env_reader import get_env


@pytest.mark.skipif(get_env("TESTING_REVISIONS_ENABLED", False), reason="Until conan config is implemented")
@pytest.mark.skipif(six.PY2, reason="v2.0: Only testing for Python 3")
class CliHelpTest(unittest.TestCase):

    def run(self, *args, **kwargs):
        with environment_append({"CONAN_V2_CLI": "1"}):
            super(CliHelpTest, self).run(*args, **kwargs)

    def test_help_command(self):
        client = TestClient()

        client.run("help")
        self.assertIn("Shows help for a specific command", client.out)

        client.run("help search")
        self.assertIn("Searches for package recipes whose name contain", client.out)
