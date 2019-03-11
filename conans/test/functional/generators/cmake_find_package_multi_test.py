import unittest

from nose.plugins import attrib


@attrib('slow')
class CMakeFindPathMultiGeneratorTest(unittest.TestCase):

    def test_native_export_multi(self):
        # PENDING, WILLING TO INTRODUCE SOME ASSETS TO THE TEST
        pass
