# coding=utf-8

import unittest
from collections import namedtuple

from conans.model.conan_file import create_requirements

MockConanFile = namedtuple("MockConanFile", ["requires", ])


class TupleTest(unittest.TestCase):

    def test_implicit_tuple(self):
        requires = "req/1.0@user/version", "req2/1.0@user/version"
        self.assertEqual(type(requires), tuple)
        conanfile = MockConanFile(requires=requires)
        r = create_requirements(conanfile)
        self.assertListEqual(list(r.keys()), ["req", "req2"])

    def test_tuple(self):
        requires = ("req/1.0@user/version", "req2/1.0@user/version")
        self.assertEqual(type(requires), tuple)
        conanfile = MockConanFile(requires=requires)
        r = create_requirements(conanfile)
        self.assertListEqual(list(r.keys()), ["req", "req2"])

    def test_config_tuple(self):
        requires = (("req/1.0@user/version", "private"), )
        self.assertEqual(type(requires), tuple)
        conanfile = MockConanFile(requires=requires)
        r = create_requirements(conanfile)
        self.assertListEqual(list(r.keys()), ["req", ])


class ListTest(unittest.TestCase):

    def test_list(self):
        requires = ["req/1.0@user/version", "req2/1.0@user/version"]
        self.assertEqual(type(requires), list)
        conanfile = MockConanFile(requires=requires)
        r = create_requirements(conanfile)
        self.assertListEqual(list(r.keys()), ["req", "req2"])

    def test_config_list(self):
        requires = [("req/1.0@user/version", "private"), ]
        self.assertEqual(type(requires), list)
        conanfile = MockConanFile(requires=requires)
        r = create_requirements(conanfile)
        self.assertListEqual(list(r.keys()), ["req", ])
