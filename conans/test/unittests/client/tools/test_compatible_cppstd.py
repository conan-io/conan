import unittest
from parameterized import parameterized

from conans.test.utils.conanfile import MockConanfile, MockSettings
from conans.errors import ConanInvalidConfiguration, ConanException

from conans.tools import compatible_cppstd


class CompatibleCppstdTest(unittest.TestCase):

    def test_user_inputs(self):
        """ Inputs with incorrect types should throw ConanException
        """
        conanfile = MockConanfile(MockSettings({}))

        with self.assertRaises(ConanException) as raises:
            compatible_cppstd(conanfile, current_cppstd=[])
        self.assertEqual(
            "current_cppstd parameter must either be a string or a digit", str(raises.exception))

        with self.assertRaises(ConanException) as raises:
            compatible_cppstd(conanfile, current_cppstd=14, min=[])
        self.assertEqual("min parameter must be a number", str(raises.exception))

        with self.assertRaises(ConanException) as raises:
            compatible_cppstd(conanfile, current_cppstd=14, max=[])
        self.assertEqual("max parameter must be a number", str(raises.exception))

        with self.assertRaises(ConanException) as raises:
            compatible_cppstd(conanfile, current_cppstd=14, forward=[])
        self.assertEqual("forward parameter must be a bool", str(raises.exception))

        with self.assertRaises(ConanException) as raises:
            compatible_cppstd(conanfile, current_cppstd=14, backward=[])
        self.assertEqual("backward parameter must be a bool", str(raises.exception))

        with self.assertRaises(ConanException) as raises:
            compatible_cppstd(conanfile, current_cppstd=14, gnu_extensions_compatible=[])
        self.assertEqual("gnu_extensions_compatible parameter must be a bool",
                         str(raises.exception))

        with self.assertRaises(ConanInvalidConfiguration) as raises:
            compatible_cppstd(conanfile, current_cppstd=10)
        self.assertIn("current_cppstd not found in the list of known cppstd values: ",
                      str(raises.exception))

        with self.assertRaises(ConanInvalidConfiguration) as raises:
            compatible_cppstd(conanfile, current_cppstd=14, min=10)
        self.assertIn("min not found in the list of known cppstd values: ",
                      str(raises.exception))

        with self.assertRaises(ConanInvalidConfiguration) as raises:
            compatible_cppstd(conanfile, current_cppstd=14, max=15)
        self.assertIn("max not found in the list of known cppstd values: ",
                      str(raises.exception))
