import unittest
from nose.plugins.attrib import attr


@attr('slow')
class CMakeFindPathMultiGeneratorTest(unittest.TestCase):

    def test_native_export_multi(self):
        # PENDING, WILLING TO INTRODUCE SOME ASSETS TO THE TEST
        pass
