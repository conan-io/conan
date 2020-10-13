# coding=utf-8

import unittest
from collections import namedtuple

import six

from conans.errors import ConanException
from conans.model.scm import _get_dict_value, SCMData


class GetDictValueTestCase(unittest.TestCase):

    def test_string_type(self):
        self.assertEqual(_get_dict_value({"str": "value"}, "str", six.string_types), "value")
        self.assertEqual(_get_dict_value({"str": u"value"}, "str", six.string_types), "value")

        def get_string():
            return "value"
        self.assertEqual(_get_dict_value({"str": get_string()}, "str", six.string_types), "value")
        self.assertEqual(_get_dict_value({"str": None}, "str", six.string_types), None)

    def test_no_string_type(self):
        str_type_name = 'str' if six.PY3 else 'basestring'
        exception_msg = "must be of type '{}' \(found '{{found}}'\)".format(str_type_name)
        with six.assertRaisesRegex(self, ConanException, exception_msg.format(found="int")):
            _get_dict_value({"str": 23}, "str", six.string_types)

        if six.PY3:  # For py2, bytes is instance of str
            with six.assertRaisesRegex(self, ConanException, exception_msg.format(found="bytes")):
                _get_dict_value({"str": b"value"}, "str", six.string_types)

        with six.assertRaisesRegex(self, ConanException, exception_msg.format(found="bool")):
            _get_dict_value({"str": True}, "str", six.string_types)

        with six.assertRaisesRegex(self, ConanException, exception_msg.format(found="function")):
            _get_dict_value({"str": lambda: "value"}, "str", six.string_types)

    def test_boolean_type(self):
        self.assertEqual(_get_dict_value({"key": True}, "key", bool), True)
        self.assertEqual(_get_dict_value({"key": False}, "key", bool), False)

    def test_no_boolean_type(self):
        with six.assertRaisesRegex(self, ConanException, "must be of type 'bool' \(found 'int'\)"):
            _get_dict_value({"key": 123}, "key", bool)

        with six.assertRaisesRegex(self, ConanException, "must be of type 'bool' \(found 'str'\)"):
            _get_dict_value({"key": "str"}, "key", bool)


class SCMDataToStringTestCase(unittest.TestCase):
    data = {"url": "http://my.url",
            "revision": 123,
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
