import unittest

from conans.client.tools import environment_append
from conans.test.utils.tools import TestClient

from configparser import ConfigParser, BasicInterpolation


class ProfileInterpolator(BasicInterpolation):
    """Interpolation which expands environment variables in values."""

    def before_get(self, parser, section, option, value, defaults):
        from collections import defaultdict
        rawval = parser.get(section, option, raw=True)
        missing_keys = defaultdict(str)
        rawval % missing_keys
        all_keys = dict(missing_keys)
        all_keys.update(parser.defaults())
        val = rawval % all_keys
        return val


class ProfileConfigParser(ConfigParser):

    def __init__(self, *args, **kargs):
        super(ConfigParser, self).__init__(interpolation=ProfileInterpolator(), *args, **kargs)

    def optionxform(self, optionstr):
        return optionstr


class ProfileTest(unittest.TestCase):

    def test_config_parser(self):
        parser1 = ProfileConfigParser()
        profile1 = """
        [env]
        bar=bar1
        zet=zet
        CXXFLAGS=-fPIC
        """
        parser1.read_string(profile1)
        p1_vars = dict(parser1.items("env"))
        self.assertDictEqual({"bar": "bar1", "CXXFLAGS": "-fPIC", "zet": "zet"}, p1_vars)

        print(p1_vars)
        parser2 = ProfileConfigParser(defaults=p1_vars)
        profile2 = """
        [env]
        foo=foo1
        bar=bar2
        CXXFLAGS=%(CXXFLAGS)s -fother
        OTHERFLAGS=%(missing_flag)s -fother
        """
        parser2.read_string(profile2)
        self.assertDictEqual({"foo": "foo1", "CXXFLAGS": "-fPIC -fother", "bar": "bar2",
                              "zet": "zet", "OTHERFLAGS": " -fother"},
                             dict(parser2.items("env")))
