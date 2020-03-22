import unittest
from parameterized import parameterized

from conans.test.utils.conanfile import MockConanfile, MockSettings
from conans.errors import ConanInvalidConfiguration, ConanException

from conans.tools import deduced_cppstd, normalized_cppstd, check_gnu_extension


class DeducedCppstdTests(unittest.TestCase):

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
    def test_returns_specified_if_present(self, cppstd):
        """ deduced_cppstd must return cppstd if it's specified settings
        """
        conanfile = self._create_conanfile("gcc", "9", "Linux", cppstd, "libstdc++")
        self.assertEqual(deduced_cppstd(conanfile), cppstd)

    def test_compiler_not_specified(self):
        """ deduced_cppstd must raise if compiler information is missing
        """
        with self.assertRaises(ConanInvalidConfiguration) as raises:
            conanfile = self._create_conanfile(None, "9", "Linux", None, "libstdc++")
            deduced_cppstd(conanfile)
        self.assertIn("compiler is not specified", str(raises.exception))

        with self.assertRaises(ConanInvalidConfiguration) as raises:
            conanfile = self._create_conanfile("gnu", None, "Linux", None, "libstdc++")
            deduced_cppstd(conanfile)
        self.assertIn("compiler.version is not specified", str(raises.exception))

    def test_unknown_compiler_declared(self):
        """ deduced_cppstd must return None if Conan lacks information about specified compiler
        """
        conanfile = self._create_conanfile("sun-cc", "5.13", "Linux", None, "libstdc++")
        self.assertEqual(deduced_cppstd(conanfile), None)


class NormalizedCppstdTests(unittest.TestCase):

    def test_user_inputs(self):
        """ Inputs with incorrect types should throw ConanException
        """
        with self.assertRaises(ConanException) as raises:
            normalized_cppstd(["gnu11", "gnu14"])
        self.assertEqual("cppstd parameter must either be a string or a digit",
                         str(raises.exception))

    def test_digit_normalization(self):
        """ normalized_cppstd must normalize digits
        """
        self.assertEqual("2017", normalized_cppstd(17))

    def test_extension_normalization(self):
        """ normalized_cppstd must normalize extensions
        """
        self.assertEqual("2017", normalized_cppstd("gnu17"))

    def test_experimental_normalization(self):
        """ normalized_cppstd must normalize exprimental versions
        """
        self.assertEqual("201z", normalized_cppstd("1z"))

    def test_old_normalization(self):
        """ normalized_cppstd must correctly normalize 98 standard
        """
        self.assertEqual("1998", normalized_cppstd("98"))


class CheckGnuExtensionTests(unittest.TestCase):

    def test_user_inputs(self):
        """ Inputs with incorrect types should throw ConanException
        """
        with self.assertRaises(ConanException) as raises:
            check_gnu_extension(["gnu11", "gnu14"])
        self.assertEqual("cppstd parameter must either be a string or a digit",
                         str(raises.exception))

    def test_check_gnu_extension(self):
        """ check_gnu_extension checks for gnu
        """
        check_gnu_extension("gnu11")

        with self.assertRaises(ConanInvalidConfiguration) as raises:
            check_gnu_extension("11")
        self.assertEqual("The cppstd GNU extension is required",
                         str(raises.exception))
