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

    def test_config_parser(self):
        from configparser import ConfigParser, BasicInterpolation

        class CustomInterpolation(BasicInterpolation):
            """Interpolation which expands environment variables in values."""

            def before_get(self, parser, section, option, value, defaults):
                rawval = parser.get(section, option, raw=True)
                val = rawval % parser.defaults()
                return val

        parser1 = ConfigParser(interpolation=CustomInterpolation())
        profile1 = """
        [env]
        bar=bar1
        zet=zet
        CXXFLAGS=-fpic
        """
        parser1.read_string(profile1)
        p1_vars = dict(parser1.items("env"))
        self.assertDictEqual({"bar": "bar1", "cxxflags": "-fpic", "zet": "zet"}, p1_vars)

        parser2 = ConfigParser(interpolation=CustomInterpolation(), defaults=p1_vars)
        profile2 = """
        [env]
        foo=foo1
        bar=bar2
        CXXFLAGS=%(cxxflags)s -fother
        OTHERFLAGS=%(otherflags)s -fother
        """
        parser2.read_string(profile2)
        self.assertDictEqual({"foo": "foo1", "cxxflags": "-fpic -fother", "bar": "bar2"},
                             dict(parser2.items("env")))
