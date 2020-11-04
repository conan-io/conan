import textwrap
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
        if section in parser.section_defaults:
            all_keys.update(parser.section_defaults[section])
        val = rawval % all_keys
        return val


class ProfileConfigParser(ConfigParser):

    def __init__(self, section_defaults=None, *args, **kargs):
        super(ConfigParser, self).__init__(interpolation=ProfileInterpolator(), delimiters=("=",),
                                           *args, **kargs)
        self.section_defaults = section_defaults or {}

    def optionxform(self, optionstr):
        return optionstr

    def items(self, *args, **kargs):  # section=_UNSET, raw=False, vars=None
        items = dict(super(ConfigParser, self).items(*args, **kargs))
        result = {}
        section = args[0] if args else None
        if section:
            if section in self.section_defaults:
                result = self.section_defaults[section]
        result.update(items)
        return result


class ProfileTest(unittest.TestCase):

    def test_env(self):
        parser1 = ProfileConfigParser()
        profile1 = textwrap.dedent("""
            [env]
            bar=bar1
            zet=zet
            CXXFLAGS=-fPIC
        """)
        parser1.read_string(profile1)
        p1_vars = dict(parser1.items("env"))
        self.assertDictEqual({"bar": "bar1", "CXXFLAGS": "-fPIC", "zet": "zet"}, p1_vars)

        parser2 = ProfileConfigParser(section_defaults=dict(parser1.items()))
        profile2 = textwrap.dedent("""
            [env]
            foo=foo1
            bar=bar2
            CXXFLAGS=%(CXXFLAGS)s -fother
            OTHERFLAGS=%(missing_flag)s -fother
        """)
        parser2.read_string(profile2)
        self.assertDictEqual({"foo": "foo1", "CXXFLAGS": "-fPIC -fother", "bar": "bar2",
                              "zet": "zet", "OTHERFLAGS": " -fother"},
                             dict(parser2.items("env")))

    def test_settings_options(self):
        parser1 = ProfileConfigParser()
        profile1 = textwrap.dedent("""
            [settings]
            os=Windows
            arch=x86
            [options]
            poco:with_zlib=True
            poco:with_openssl=True
        """)
        parser1.read_string(profile1)
        p1_settings = dict(parser1.items("settings"))
        self.assertDictEqual({"os": "Windows", "arch": "x86"}, p1_settings)
        p1_options = dict(parser1.items("options"))
        self.assertDictEqual({"poco:with_zlib": "True", "poco:with_openssl": "True"}, p1_options)

        parser2 = ProfileConfigParser(section_defaults=dict(parser1.items()))
        profile2 = textwrap.dedent("""
            [settings]
            arch=x86_64
            build_type=Release
            [options]
            poco:with_openssl=False
            poco:with_other=False
        """)
        parser2.read_string(profile2)
        p2_settings = dict(parser2.items("settings"))
        self.assertDictEqual({"os": "Windows", "arch": "x86_64", "build_type": "Release"},
                             p2_settings)
        p2_options = dict(parser2.items("options"))
        self.assertDictEqual({"poco:with_zlib": "True", "poco:with_openssl": "False",
                              "poco:with_other": "False"},
                             p2_options)
