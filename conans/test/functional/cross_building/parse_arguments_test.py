# coding=utf-8

import unittest
import argparse
from conans.client.command import _add_common_install_arguments
from parameterized.parameterized import parameterized_class

from conans.client.tools import environment_append, save
from conans.test.utils.deprecation import catch_deprecation_warning
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient


@parameterized_class([{"argument": ["env", "-e", "--env"]},
                      {"argument": ["options", "-o", "--options"]},
                      {"argument": ["profile", "-pr", "--profile"]},
                      {"argument": ["settings", "-s", "--settings"]}])
class ArgsParseProfileTest(unittest.TestCase):
    """ Check argparse for profile arguments """

    def setUp(self):
        self.item, self.short_arg, self.long_arg = self.argument
        self.args_dest_build = '{}_build'.format(self.item)
        self.args_dest_host = '{}_host'.format(self.item)

    def _run_parse(self, *args):
        parser = argparse.ArgumentParser()
        _add_common_install_arguments(parser, build_help=False)
        parsed_args = parser.parse_args(*args)
        build = getattr(parsed_args, self.args_dest_build)
        host = getattr(parsed_args, self.args_dest_host)
        return build, host

    def test_default(self):
        """ The old '--settings', '--profile',... refers to the build machine """
        build, host = self._run_parse([self.long_arg, "it1"])
        self.assertListEqual(build, ["it1"])
        self.assertIsNone(host)

        build, host = self._run_parse([self.long_arg, "it1", self.short_arg, "it2"])
        self.assertListEqual(build, ["it1", "it2"])
        self.assertIsNone(host)

    def test_build_machine(self):
        """ If provided with build suffix (':b', ':build'), those correspond to the build machine """
        long_arg = "{}:build".format(self.long_arg)
        short_arg = "{}:b".format(self.short_arg)

        build, host = self._run_parse([long_arg, "it1"])
        self.assertListEqual(build, ["it1"])
        self.assertIsNone(host)

        build, host = self._run_parse([long_arg, "it1", short_arg, "it2"])
        self.assertListEqual(build, ["it1", "it2"])
        self.assertIsNone(host)

    def test_mix_old_and_build_machine(self):
        """ Old arguments and new ':build' ones are composable """
        new_long_arg = "{}:build".format(self.long_arg)
        new_short_arg = "{}:b".format(self.short_arg)

        build, host = self._run_parse([new_long_arg, "it1", self.long_arg, "it2",
                                       new_short_arg, "it3", self.short_arg, "it4"])
        self.assertListEqual(build, ["it1", "it2", "it3", "it4"])
        self.assertIsNone(host)

    def test_host_machine(self):
        """ If provided with host suffix (':h', ':host'), those correspond to the host machine """
        long_arg = "{}:host".format(self.long_arg)
        short_arg = "{}:h".format(self.short_arg)

        build, host = self._run_parse([long_arg, "it1"])
        self.assertListEqual(host, ["it1"])
        self.assertIsNone(build)

        build, host = self._run_parse([long_arg, "it1", short_arg, "it2"])
        self.assertListEqual(host, ["it1", "it2"])
        self.assertIsNone(build)

    def test_build_and_host(self):
        """ Of course, I can provide build and host in the same command line """
        build, host = self._run_parse(["{}:build".format(self.long_arg), "b1",
                                       "{}:host".format(self.long_arg), "h1"])
        self.assertListEqual(build, ["b1"])
        self.assertListEqual(host, ["h1"])
