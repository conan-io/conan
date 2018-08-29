import unittest
import os


class ConanTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        os.environ["CONAN_RECIPE_LINTER"] = "False"
        super(ConanTestCase, cls).setUpClass()

    @classmethod
    def tearDownClass(cls):
        del os.environ["CONAN_RECIPE_LINTER"]
        super(ConanTestCase, cls).tearDownClass()
