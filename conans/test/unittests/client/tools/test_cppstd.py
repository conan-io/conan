import unittest
from conans.tools import Cppstd


class CppstdTest(unittest.TestCase):

    def test_cppstd_version(self):
        self.assertTrue(Cppstd("11") < Cppstd("14"))
        self.assertTrue(Cppstd("gnu17") == Cppstd("17"))
        self.assertFalse(Cppstd("gnu17") == Cppstd("14"))
        self.assertTrue(Cppstd("gnu17") > Cppstd("gnu14"))
        self.assertTrue(Cppstd("gnu17") < Cppstd("20"))
        self.assertTrue(Cppstd("gnu17") < Cppstd("gnu20"))
