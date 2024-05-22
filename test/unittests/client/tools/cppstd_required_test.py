import unittest
from mock import mock
from parameterized import parameterized

from conan.tools.build import check_max_cppstd, check_min_cppstd, valid_max_cppstd, valid_min_cppstd
from conan.test.utils.mocks import MockSettings, ConanFileMock
from conans.errors import ConanInvalidConfiguration, ConanException


def _create_conanfile(compiler, version, os, cppstd, libcxx=None):
    settings = MockSettings({"arch": "x86_64",
                             "build_type": "Debug",
                             "os": os,
                             "compiler": compiler,
                             "compiler.version": version,
                             "compiler.cppstd": cppstd})
    if libcxx:
        settings.values["compiler.libcxx"] = libcxx
    conanfile = ConanFileMock(settings)
    return conanfile


class UserInputTests(unittest.TestCase):

    def test_check_cppstd_type(self):
        """ cppstd must be a number
        """
        conanfile = ConanFileMock(MockSettings({}))
        with self.assertRaises(ConanException) as raises:
            check_min_cppstd(conanfile, "gnu17", False)
        self.assertEqual("cppstd parameter must be a number", str(raises.exception))


class CheckMinCppStdTests(unittest.TestCase):

    @parameterized.expand(["98", "11", "14", "17"])
    def test_check_min_cppstd_from_settings(self, cppstd):
        """ check_min_cppstd must accept cppstd less/equal than cppstd in settings
        """
        conanfile = _create_conanfile("gcc", "9", "Linux", "17", "libstdc++")
        check_min_cppstd(conanfile, cppstd, False)

    @parameterized.expand(["98", "11", "14"])
    def test_check_min_cppstd_from_outdated_settings(self, cppstd):
        """ check_min_cppstd must raise when cppstd is greater when supported on settings
        """
        conanfile = _create_conanfile("gcc", "9", "Linux", cppstd, "libstdc++")
        with self.assertRaises(ConanInvalidConfiguration) as raises:
            check_min_cppstd(conanfile, "17", False)
        self.assertEqual("Current cppstd ({}) is lower than the required C++ standard "
                         "(17).".format(cppstd), str(raises.exception))

    @parameterized.expand(["98", "11", "14", "17"])
    def test_check_min_cppstd_from_settings_with_extension(self, cppstd):
        """ current cppstd in settings must has GNU extension when extensions is enabled
        """
        conanfile = _create_conanfile("gcc", "9", "Linux", "gnu17", "libstdc++")
        check_min_cppstd(conanfile, cppstd, True)

        conanfile.settings.values["compiler.cppstd"] = "17"
        with self.assertRaises(ConanException) as raises:
            check_min_cppstd(conanfile, cppstd, True)
        self.assertEqual("The cppstd GNU extension is required", str(raises.exception))

    def test_check_min_cppstd_unsupported_standard(self):
        """ check_min_cppstd must raise when the compiler does not support a standard
        """
        conanfile = _create_conanfile("gcc", "9", "Linux", "gnu14", "libstdc++")
        with self.assertRaises(ConanInvalidConfiguration) as raises:
            check_min_cppstd(conanfile, "42", False)
        self.assertEqual("Current cppstd (gnu14) is lower than the required C++ standard (42).",
                         str(raises.exception))

    def test_check_min_cppstd_gnu_compiler_extension(self):
        """ Current compiler must support GNU extension on Linux when extensions is required
        """
        conanfile = _create_conanfile("gcc", "9", "Linux", "17", "libstdc++")
        with mock.patch("platform.system", mock.MagicMock(return_value="Linux")):
            with self.assertRaises(ConanException) as raises:
                check_min_cppstd(conanfile, "17", True)
            self.assertEqual("The cppstd GNU extension is required", str(raises.exception))


class ValidMinCppstdTests(unittest.TestCase):

    @parameterized.expand(["98", "11", "14", "17"])
    def test_valid_min_cppstd_from_settings(self, cppstd):
        """ valid_min_cppstd must accept cppstd less/equal than cppstd in settings
        """
        conanfile = _create_conanfile("gcc", "9", "Linux", "17", "libstdc++")
        self.assertTrue(valid_min_cppstd(conanfile, cppstd, False))

    @parameterized.expand(["98", "11", "14"])
    def test_valid_min_cppstd_from_outdated_settings(self, cppstd):
        """ valid_min_cppstd returns False when cppstd is greater when supported on settings
        """
        conanfile = _create_conanfile("gcc", "9", "Linux", cppstd, "libstdc++")
        self.assertFalse(valid_min_cppstd(conanfile, "17", False))

    @parameterized.expand(["98", "11", "14", "17"])
    def test_valid_min_cppstd_from_settings_with_extension(self, cppstd):
        """ valid_min_cppstd must returns True when current cppstd in settings has GNU extension and
            extensions is enabled
        """
        conanfile = _create_conanfile("gcc", "9", "Linux", "gnu17", "libstdc++")
        self.assertTrue(valid_min_cppstd(conanfile, cppstd, True))

        conanfile.settings.values["compiler.cppstd"] = "17"
        self.assertFalse(valid_min_cppstd(conanfile, cppstd, True))

    def test_valid_min_cppstd_unsupported_standard(self):
        """ valid_min_cppstd must returns False when the compiler does not support a standard
        """
        conanfile = _create_conanfile("gcc", "9", "Linux", "17", "libstdc++")
        self.assertFalse(valid_min_cppstd(conanfile, "42", False))

    def test_valid_min_cppstd_gnu_compiler_extension(self):
        """ valid_min_cppstd must returns False when current compiler does not support GNU extension
            on Linux and extensions is required
        """
        conanfile = _create_conanfile("gcc", "9", "Linux", "gnu1z", "libstdc++")
        with mock.patch("platform.system", mock.MagicMock(return_value="Linux")):
            self.assertFalse(valid_min_cppstd(conanfile, "20", True))

    @parameterized.expand(["98", "11", "14", "17"])
    def test_min_cppstd_mingw_windows(self, cppstd):
        """ GNU extensions HAS effect on Windows when running a cross-building for Linux
        """
        with mock.patch("platform.system", mock.MagicMock(return_value="Windows")):
            conanfile = _create_conanfile("gcc", "9", "Linux", "gnu17", "libstdc++")
            self.assertTrue(valid_min_cppstd(conanfile, cppstd, True))

            conanfile.settings.values["compiler.cppstd"] = "17"
            self.assertFalse(valid_min_cppstd(conanfile, cppstd, True))


class CheckMaxCppStdTests(unittest.TestCase):

    @parameterized.expand(["98", "11", "14", "17"])
    def test_check_max_cppstd_from_settings(self, cppstd):
        """ check_max_cppstd must accept cppstd higher/equal than cppstd in settings
        """
        conanfile = _create_conanfile("gcc", "9", "Linux", "98", "libstdc++")
        check_max_cppstd(conanfile, cppstd, False)

    @parameterized.expand(["11", "14", "17"])
    def test_check_max_cppstd_from_outdated_settings(self, cppstd):
        """ check_max_cppstd must raise when cppstd is higher when supported on settings
        """
        conanfile = _create_conanfile("gcc", "9", "Linux", cppstd, "libstdc++")
        with self.assertRaises(ConanInvalidConfiguration) as raises:
            check_max_cppstd(conanfile, "98", False)
        self.assertEqual("Current cppstd ({}) is higher than the required C++ standard "
                         "(98).".format(cppstd), str(raises.exception))

    @parameterized.expand(["98", "11", "14", "17"])
    def test_check_max_cppstd_from_settings_with_extension(self, cppstd):
        """ current cppstd in settings must have GNU extension when extensions is enabled
        """
        conanfile = _create_conanfile("gcc", "9", "Linux", "gnu98", "libstdc++")
        check_max_cppstd(conanfile, cppstd, True)

        conanfile.settings.values["compiler.cppstd"] = "98"
        with self.assertRaises(ConanException) as raises:
            check_max_cppstd(conanfile, cppstd, True)
        self.assertEqual("The cppstd GNU extension is required", str(raises.exception))

    def test_check_max_cppstd_unsupported_standard(self):
        """ check_max_cppstd must raise when the compiler does not support a standard
        """
        conanfile = _create_conanfile("gcc", "9", "Linux", "gnu17", "libstdc++")
        with self.assertRaises(ConanInvalidConfiguration) as raises:
            check_max_cppstd(conanfile, "16", False)
        self.assertEqual("Current cppstd (gnu17) is higher than the required C++ standard (16).",
                         str(raises.exception))

    def test_check_max_cppstd_gnu_compiler_extension(self):
        """ Current compiler must support GNU extension on Linux when extensions is required
        """
        conanfile = _create_conanfile("gcc", "9", "Linux", "17", "libstdc++")
        with mock.patch("platform.system", mock.MagicMock(return_value="Linux")):
            with self.assertRaises(ConanException) as raises:
                check_max_cppstd(conanfile, "17", True)
            self.assertEqual("The cppstd GNU extension is required", str(raises.exception))


class ValidMaxCppstdTests(unittest.TestCase):

    @parameterized.expand(["98", "11", "14", "17"])
    def test_valid_max_cppstd_from_settings(self, cppstd):
        """ valid_max_cppstd must accept cppstd higher/equal than cppstd in settings
        """
        conanfile = _create_conanfile("gcc", "9", "Linux", "98", "libstdc++")
        self.assertTrue(valid_max_cppstd(conanfile, cppstd, False))

    @parameterized.expand(["11", "14", "17"])
    def test_valid_max_cppstd_from_outdated_settings(self, cppstd):
        """ valid_max_cppstd return False when cppstd is greater when supported on settings
        """
        conanfile = _create_conanfile("gcc", "9", "Linux", cppstd, "libstdc++")
        self.assertFalse(valid_max_cppstd(conanfile, "98", False))

    @parameterized.expand(["98", "11", "14", "17"])
    def test_valid_max_cppstd_from_settings_with_extension(self, cppstd):
        """ valid_max_cppstd must return True when current cppstd in settings has GNU extension and
            extensions is enabled
        """
        conanfile = _create_conanfile("gcc", "9", "Linux", "gnu98", "libstdc++")
        self.assertTrue(valid_max_cppstd(conanfile, cppstd, True))

        conanfile.settings.values["compiler.cppstd"] = "98"
        self.assertFalse(valid_max_cppstd(conanfile, cppstd, True))

    def test_valid_max_cppstd_unsupported_standard(self):
        """ valid_max_cppstd must return False when the compiler does not support a standard
        """
        conanfile = _create_conanfile("gcc", "9", "Linux", "17", "libstdc++")
        self.assertFalse(valid_max_cppstd(conanfile, "16", False))

    def test_valid_max_cppstd_gnu_compiler_extension(self):
        """ valid_max_cppstd must return False when current compiler does not support GNU extension
            on Linux and extensions is required
        """
        conanfile = _create_conanfile("gcc", "9", "Linux", "gnu17", "libstdc++")
        with mock.patch("platform.system", mock.MagicMock(return_value="Linux")):
            self.assertFalse(valid_max_cppstd(conanfile, "14", True))

    @parameterized.expand(["98", "11", "14", "17"])
    def test_max_cppstd_mingw_windows(self, cppstd):
        """ GNU extensions HAS effect on Windows when running a cross-building for Linux
        """
        with mock.patch("platform.system", mock.MagicMock(return_value="Windows")):
            conanfile = _create_conanfile("gcc", "9", "Linux", "gnu98", "libstdc++")
            self.assertTrue(valid_max_cppstd(conanfile, cppstd, True))

            conanfile.settings.values["compiler.cppstd"] = "98"
            self.assertFalse(valid_max_cppstd(conanfile, cppstd, True))
