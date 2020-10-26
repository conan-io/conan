import unittest

from conans.client.tools import environment_append
from conans.test.utils.tools import TestClient


class ProfileTest(unittest.TestCase):

    def test_env_var_with_variable_substitution(self):
        client = TestClient()
        profile = """
        MY_VAR=whatever
        [env]
        foo=$MY_VAR
        bar=${MY_VAR}
        wot=%MY_VAR%
        """
        client.save({"profile": profile})
        client.run("new test/1.0")
        with environment_append({"MY_VAR": "new value"}):
            client.run("profile show profile")
        self.assertIn("foo=whatever", client.out)
        self.assertIn("bar=new value", client.out)
        self.assertIn("wot=new value", client.out)

    def test_env_var_without_variable_substitution(self):
        client = TestClient()
        profile = """
        [env]
        foo=$MY_VAR
        bar=other;${MY_VAR}
        zet=$KK
        """
        client.save({"profile": profile})
        client.run("new test/1.0")
        with environment_append({"MY_VAR": "new value"}):
            client.run("profile show profile")
        self.assertIn("foo=new value", client.out)
        self.assertIn("bar=other;new value", client.out)
        self.assertIn("zet=$KK", client.out)
        print(client.out)
