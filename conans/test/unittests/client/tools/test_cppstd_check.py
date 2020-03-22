import unittest
from parameterized import parameterized

from conans.test.utils.conanfile import MockConanfile, MockSettings
from conans.errors import ConanInvalidConfiguration, ConanException

from conans.tools import check_cppstd


class CheckCppstdTests(unittest.TestCase):

    def test_user_inputs(self):
        """ Inputs with incorrect types should throw ConanException
        """
        conanfile = MockConanfile(MockSettings({}))

        with self.assertRaises(ConanException) as raises:
            check_cppstd(conanfile, minimum="abcdefg")
        self.assertEqual("minimum parameter must be a number", str(raises.exception))

        with self.assertRaises(ConanException) as raises:
            check_cppstd(conanfile, maximum="abcdefg")
        self.assertEqual("maximum parameter must be a number", str(raises.exception))

        with self.assertRaises(ConanException) as raises:
            check_cppstd(conanfile, minimum="20", maximum="11")
        self.assertEqual("minimum parameter is bigger than the maximum parameter",
                         str(raises.exception))

        with self.assertRaises(ConanException) as raises:
            check_cppstd(conanfile, excludes={})
        self.assertEqual("excludes parameter must be a list", str(raises.exception))

        with self.assertRaises(ConanException) as raises:
            check_cppstd(conanfile, gnu_extensions="abcdefg")
        self.assertEqual("gnu_extensions parameter must be a bool", str(raises.exception))

        with self.assertRaises(ConanException) as raises:
            check_cppstd(conanfile, strict="abcdefg")
        self.assertEqual("strict parameter must be a bool", str(raises.exception))

    def _create_conanfile(self, compiler, version, os, cppstd, libcxx=None):
        settings = MockSettings({"arch": "x86_64",
                                 "build_type": "Debug",
                                 "os": os,
                                 "compiler": compiler,
                                 "compiler.version": version,
                                 "compiler.cppstd": cppstd})
        if libcxx:
            settings.values["compiler.libcxx"] = libcxx
        conanfile = MockConanfile(settings)
        return conanfile

    @parameterized.expand(["98", "11", "14", "17"])
    def test_check_valid_ranges(self, cppstd):
        """ check_cppstd must accept cppstd in the given range
        """
        conanfile = self._create_conanfile("gcc", "9", "Linux", cppstd, "libstdc++")
        check_cppstd(conanfile, minimum="98")
        check_cppstd(conanfile, minimum="98", maximum="17")
        check_cppstd(conanfile, maximum="17")
        check_cppstd(conanfile, excludes=["20"])
        check_cppstd(conanfile, minimum="98", maximum="17", excludes=["20"])

    @parameterized.expand(["11", "14", "17"])
    def test_check_invalid_ranges(self, cppstd):
        """ check_cppstd should not accept cppstd out of the given range
        """
        conanfile = self._create_conanfile("gcc", "9", "Linux", cppstd, "libstdc++")

        with self.assertRaises(ConanInvalidConfiguration) as raises:
            check_cppstd(conanfile, minimum="20")
        self.assertIn("Current cppstd ({}) is less than the minimum required".format(
            cppstd), str(raises.exception))

        with self.assertRaises(ConanInvalidConfiguration) as raises:
            check_cppstd(conanfile, maximum="98")
        self.assertIn("Current cppstd ({}) is higher than the maximum required".format(
            cppstd), str(raises.exception))

        with self.assertRaises(ConanInvalidConfiguration) as raises:
            check_cppstd(conanfile, excludes=["11", "14", "17"])
        self.assertIn("Current cppstd ({}) is excluded from requirements".format(
            cppstd), str(raises.exception))

        with self.assertRaises(ConanInvalidConfiguration) as raises:
            check_cppstd(conanfile, minimum="11", maximum="20", excludes=["11", "14", "17"])
        self.assertIn("Current cppstd ({}) is excluded from requirements".format(
            cppstd), str(raises.exception))

    @parameterized.expand(["98", "11", "14", "17"])
    def test_check_gnu_extension(self, cppstd):
        """ current cppstd in settings must has GNU extension when extensions are enabled
        """
        conanfile = self._create_conanfile("gcc", "9", "Linux", "gnu17", "libstdc++")
        check_cppstd(conanfile, minimum=cppstd, gnu_extensions=True)

        conanfile.settings.values["compiler.cppstd"] = "17"
        with self.assertRaises(ConanException) as raises:
            check_cppstd(conanfile, minimum=cppstd, gnu_extensions=True)
        self.assertEqual("The cppstd GNU extension is required", str(raises.exception))

    def test_compiler_not_specified(self):
        """ check_cppstd must raise if compiler information is missing
        """
        with self.assertRaises(ConanInvalidConfiguration) as raises:
            conanfile = self._create_conanfile(None, "9", "Linux", None, "libstdc++")
            check_cppstd(conanfile, minimum="14")
        self.assertIn("compiler is not specified", str(raises.exception))

        with self.assertRaises(ConanInvalidConfiguration) as raises:
            conanfile = self._create_conanfile("gnu", None, "Linux", None, "libstdc++")
            check_cppstd(conanfile, minimum="14")
        self.assertIn("compiler.version is not specified", str(raises.exception))

    def test_check_compiler_information_is_missing(self):
        """ check_cppstd must warn when information about compiler is missing by default
        """
        conanfile = self._create_conanfile("something_else", "5", "Linux", None, "libstdc++")
        check_cppstd(conanfile, minimum="14")
        self.assertIn(
            "WARN: Default standard version information is missing for the current compiler", conanfile.output)

    def test_check_compiler_strict(self):
        """ check_cppstd must raise when information about compiler is missing
            only if the strict mode is enabled
        """
        conanfile = self._create_conanfile("something_else", "5", "Linux", None, "libstdc++")
        with self.assertRaises(ConanInvalidConfiguration) as raises:
            check_cppstd(conanfile, minimum="14", strict=True)
        self.assertEqual(
            "Default standard version information is missing for the current compiler", str(raises.exception))
