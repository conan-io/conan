import unittest

from conans.client.build.compilers_info import (available_cppstd_versions, cppstd_default,
                                                cppstd_flag)


class CompilersInfoTest(unittest.TestCase):

    def test_available_standards(self):
        res = available_cppstd_versions("Visual Studio", "17")
        self.assertEquals(res, ["14", "17"])

        res = available_cppstd_versions("Visual Studio", "14")
        self.assertEquals(res, ["14", "17"])

        res = available_cppstd_versions("Visual Studio", "12")
        self.assertEquals(res, [])

        res = available_cppstd_versions("Visual Studio", None)
        self.assertEquals(res, [])

    def default_standard_test(self):
        res = cppstd_default("Visual Studio", "12")
        self.assertEquals(res, None)

        res = cppstd_default("Visual Studio", "15")
        self.assertEquals(res, "14")

        res = cppstd_default("Visual Studio", "17")
        self.assertEquals(res, "14")

        res = cppstd_default("gcc", "5.4")
        self.assertEquals(res, "98gnu")

        res = cppstd_default("clang", "5")
        self.assertEquals(res, "98")

        res = cppstd_default("gcc", "6.3")
        self.assertEquals(res, "14gnu")

    def edge_cases_cppstd_test(self):
        res = cppstd_flag("gcc", "4.9", "17")
        self.assertEquals(res, None)

        res = cppstd_flag("gcc", "4.9", "14")
        self.assertEquals(res, "-std=c++14")

        res = cppstd_flag("gcc", "4.8", "14")
        self.assertEquals(res, "-std=c++1y")

        res = cppstd_flag("gcc", "5.1", "17")
        self.assertEquals(res, "-std=c++1z")

        res = cppstd_flag("clang", "2.0", "11")
        self.assertEquals(res, None)

        res = cppstd_flag("clang", "2.1", "11")
        self.assertEquals(res, "-std=c++0x")

        res = cppstd_flag("clang", "3.1", "11")
        self.assertEquals(res, "-std=c++11")

        res = cppstd_flag("clang", "3.4", "14")
        self.assertEquals(res, "-std=c++1y")

        res = cppstd_flag("clang", "3.4", "17")
        self.assertEquals(res, None)

        res = cppstd_flag("clang", "3.5", "14")
        self.assertEquals(res, "-std=c++14")

        res = cppstd_flag("clang", "3.5", "17")
        self.assertEquals(res, "-std=c++1z")
