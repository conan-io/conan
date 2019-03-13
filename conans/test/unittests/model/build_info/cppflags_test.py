# coding=utf-8

import unittest
import warnings

from conans.model.build_info import _CppInfo


class CppFlagsTest(unittest.TestCase):
    """ Test that deprecated 'cppflags' still works (keep backwards compatibility) """

    def test_use_cxxflags(self):
        """ Changes in cxxflags get reflected in cppflags """

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            cpp_info = _CppInfo()
            cpp_info.cxxflags = "flags"
            self.assertEqual(cpp_info.cppflags, "flags")
            self.assertEqual(cpp_info.cxxflags, cpp_info.cppflags)

            cpp_info.cxxflags = None
            self.assertEqual(cpp_info.cppflags, None)
            self.assertEqual(cpp_info.cxxflags, cpp_info.cppflags)

            self.assertEqual(len(w), 4)
            self.assertTrue(issubclass(w[0].category, DeprecationWarning))

    def test_use_cppflags(self):
        """ Changes in cppflags get reflected in cxxflags """

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            cpp_info = _CppInfo()

            cpp_info.cppflags = "flags"
            self.assertEqual(cpp_info.cxxflags, "flags")
            self.assertEqual(cpp_info.cxxflags, cpp_info.cppflags)

            cpp_info.cppflags = None
            self.assertEqual(cpp_info.cxxflags, None)
            self.assertEqual(cpp_info.cxxflags, cpp_info.cppflags)

            self.assertEqual(len(w), 4)
            self.assertTrue(issubclass(w[0].category, DeprecationWarning))

