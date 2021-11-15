# coding=utf-8
import mock
import unittest

from conans.util.env_reader import get_env


class GetEnvTest(unittest.TestCase):
    environment = {"EMPTY_LIST": "",
                   "LIST": "a,b,c,d"}

    def test_environment(self):
        """ Ensure that we are using os.environment if no argument is passed """
        with mock.patch("os.environ.get", return_value="zzz"):
            a = get_env("whatever", default=None)
        self.assertEqual(a, "zzz")

    def test_list_empty(self):
        r = get_env("EMPTY_LIST", default=list(), environment=self.environment)
        self.assertEqual(r, [])

        r = get_env("NON-EXISTING-LIST", default=list(), environment=self.environment)
        self.assertEqual(r, [])

    def test_list(self):
        r = get_env("LIST", default=list(), environment=self.environment)
        self.assertEqual(r, ["a", "b", "c", "d"])
