# coding=utf-8

import unittest
from collections import namedtuple

from conans.errors import ConanException
from conans.model.scm import _get_dict_value, SCMData


class GetDictValueTestCase(unittest.TestCase):

    def test_string_type(self):
        self.assertEqual(_get_dict_value({"str": "value"}, "str", str), "value")
        self.assertEqual(_get_dict_value({"str": u"value"}, "str", str), "value")

        def get_string():
            return "value"
        self.assertEqual(_get_dict_value({"str": get_string()}, "str", str), "value")
        self.assertEqual(_get_dict_value({"str": None}, "str", str), None)

    def test_no_string_type(self):
        exception_msg = "must be of type 'str' \(found '{found}'\)"
        with self.assertRaisesRegex(ConanException, exception_msg.format(found="int")):
            _get_dict_value({"str": 23}, "str", str)

        with self.assertRaisesRegex(ConanException, exception_msg.format(found="bytes")):
            _get_dict_value({"str": b"value"}, "str", str)

        with self.assertRaisesRegex(ConanException, exception_msg.format(found="bool")):
            _get_dict_value({"str": True}, "str", str)

        with self.assertRaisesRegex(ConanException, exception_msg.format(found="function")):
            _get_dict_value({"str": lambda: "value"}, "str", str)

    def test_boolean_type(self):
        self.assertEqual(_get_dict_value({"key": True}, "key", bool), True)
        self.assertEqual(_get_dict_value({"key": False}, "key", bool), False)

    def test_no_boolean_type(self):
        with self.assertRaisesRegex(ConanException, "must be of type 'bool' \(found 'int'\)"):
            _get_dict_value({"key": 123}, "key", bool)

        with self.assertRaisesRegex(ConanException, "must be of type 'bool' \(found 'str'\)"):
            _get_dict_value({"key": "str"}, "key", bool)


class SCMDataToStringTestCase(unittest.TestCase):
    data = {"url": "http://my.url",
            "revision": "123",
            "shallow": False,
            "username": 'weir"d',
            "type": "weir\"d",
            "password": "don't"}

    def test_scmdata_string(self):
        fake_class = namedtuple("Conanfile", ["scm"])
        conanfile = fake_class(scm=self.data)

        self.assertEqual(str(SCMData(conanfile)), '{"password": "don\'t", "revision": "123",'
                                                  ' "shallow": False, "type": "weir\\"d",'
                                                  ' "url": "http://my.url", "username": "weir\\"d"}')
