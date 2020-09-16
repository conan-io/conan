import unittest
from mock import mock
from parameterized import parameterized

from conans.test.utils.mocks import MockSettings, MockConanfile
from conans.client.tools import OSInfo
from conans.errors import ConanInvalidConfiguration, ConanException

from conans.tools import check_min_cppstd, valid_min_cppstd


class UserInputTests(unittest.TestCase):

    def test_check_cppstd_type(self):
        """ cppstd must be a number
        """
        conanfile = MockConanfile(MockSettings({}))
        with self.assertRaises(ConanException) as raises:
            check_min_cppstd(conanfile, "gnu17", False)
        self.assertEqual("cppstd parameter must be a number", str(raises.exception))


class CheckMinCppStdTests(unittest.TestCase):

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
    def test_check_min_cppstd_from_settings(self, cppstd):
        """ check_min_cppstd must accept cppstd less/equal than cppstd in settings
        """
        conanfile = self._create_conanfile("gcc", "9", "Linux", "17", "libstdc++")
        check_min_cppstd(conanfile, cppstd, False)

    @parameterized.expand(["98", "11", "14"])
    def test_check_min_cppstd_from_outdated_settings(self, cppstd):
        """ check_min_cppstd must raise when cppstd is greater when supported on settings
        """
        conanfile = self._create_conanfile("gcc", "9", "Linux", cppstd, "libstdc++")
        with self.assertRaises(ConanInvalidConfiguration) as raises:
            check_min_cppstd(conanfile, "17", False)
        self.assertEqual("Current cppstd ({}) is lower than the required C++ standard "
                         "(17).".format(cppstd), str(raises.exception))

    @parameterized.expand(["98", "11", "14", "17"])
    def test_check_min_cppstd_from_settings_with_extension(self, cppstd):
        """ current cppstd in settings must has GNU extension when extensions is enabled
        """
        conanfile = self._create_conanfile("gcc", "9", "Linux", "gnu17", "libstdc++")
        check_min_cppstd(conanfile, cppstd, True)

        conanfile.settings.values["compiler.cppstd"] = "17"
        with self.assertRaises(ConanException) as raises:
            check_min_cppstd(conanfile, cppstd, True)
        self.assertEqual("The cppstd GNU extension is required", str(raises.exception))

    def test_check_min_cppstd_unsupported_standard(self):
        """ check_min_cppstd must raise when the compiler does not support a standard
        """
        conanfile = self._create_conanfile("gcc", "9", "Linux", None, "libstdc++")
        with self.assertRaises(ConanInvalidConfiguration) as raises:
            check_min_cppstd(conanfile, "42", False)
        self.assertEqual("Current cppstd (gnu14) is lower than the required C++ standard (42).",
                         str(raises.exception))

    def test_check_min_cppstd_gnu_compiler_extension(self):
        """ Current compiler must support GNU extension on Linux when extensions is required
        """
        conanfile = self._create_conanfile("gcc", "9", "Linux", None, "libstdc++")
        with mock.patch("platform.system", mock.MagicMock(return_value="Linux")):
            with mock.patch.object(OSInfo, '_get_linux_distro_info'):
                with mock.patch("conans.client.tools.settings.cppstd_default", return_value="17"):
                    with self.assertRaises(ConanException) as raises:
                        check_min_cppstd(conanfile, "17", True)
                    self.assertEqual("The cppstd GNU extension is required", str(raises.exception))

    def test_no_compiler_declared(self):
        conanfile = self._create_conanfile(None, None, "Linux", None, "libstdc++")
        with self.assertRaises(ConanException) as raises:
            check_min_cppstd(conanfile, "14", False)
        self.assertEqual("Could not obtain cppstd because there is no declared compiler in the "
                         "'settings' field of the recipe.", str(raises.exception))

    def test_unknown_compiler_declared(self):
        conanfile = self._create_conanfile("sun-cc", "5.13", "Linux", None, "libstdc++")
        with self.assertRaises(ConanInvalidConfiguration) as raises:
            check_min_cppstd(conanfile, "14", False)
        self.assertEqual("Could not detect the current default cppstd for "
                         "the compiler sun-cc-5.13.", str(raises.exception))


class ValidMinCppstdTests(unittest.TestCase):

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
    def test_valid_min_cppstd_from_settings(self, cppstd):
        """ valid_min_cppstd must accept cppstd less/equal than cppstd in settings
        """
        conanfile = self._create_conanfile("gcc", "9", "Linux", "17", "libstdc++")
        self.assertTrue(valid_min_cppstd(conanfile, cppstd, False))

    @parameterized.expand(["98", "11", "14"])
    def test_valid_min_cppstd_from_outdated_settings(self, cppstd):
        """ valid_min_cppstd returns False when cppstd is greater when supported on settings
        """
        conanfile = self._create_conanfile("gcc", "9", "Linux", cppstd, "libstdc++")
        self.assertFalse(valid_min_cppstd(conanfile, "17", False))

    @parameterized.expand(["98", "11", "14", "17"])
    def test_valid_min_cppstd_from_settings_with_extension(self, cppstd):
        """ valid_min_cppstd must returns True when current cppstd in settings has GNU extension and
            extensions is enabled
        """
        conanfile = self._create_conanfile("gcc", "9", "Linux", "gnu17", "libstdc++")
        self.assertTrue(valid_min_cppstd(conanfile, cppstd, True))

        conanfile.settings.values["compiler.cppstd"] = "17"
        self.assertFalse(valid_min_cppstd(conanfile, cppstd, True))

    def test_valid_min_cppstd_unsupported_standard(self):
        """ valid_min_cppstd must returns False when the compiler does not support a standard
        """
        conanfile = self._create_conanfile("gcc", "9", "Linux", None, "libstdc++")
        self.assertFalse(valid_min_cppstd(conanfile, "42", False))

    def test_valid_min_cppstd_gnu_compiler_extension(self):
        """ valid_min_cppstd must returns False when current compiler does not support GNU extension
            on Linux and extensions is required
        """
        conanfile = self._create_conanfile("gcc", "9", "Linux", None, "libstdc++")
        with mock.patch("platform.system", mock.MagicMock(return_value="Linux")):
            with mock.patch.object(OSInfo, '_get_linux_distro_info'):
                with mock.patch("conans.client.tools.settings.cppstd_default", return_value="gnu1z"):
                    self.assertFalse(valid_min_cppstd(conanfile, "20", True))

    @parameterized.expand(["98", "11", "14", "17"])
    def test_min_cppstd_mingw_windows(self, cppstd):
        """ GNU extensions HAS effect on Windows when running a cross-building for Linux
        """
        with mock.patch("platform.system", mock.MagicMock(return_value="Windows")):
            conanfile = self._create_conanfile("gcc", "9", "Linux", "gnu17", "libstdc++")
            self.assertTrue(valid_min_cppstd(conanfile, cppstd, True))

            conanfile.settings.values["compiler.cppstd"] = "17"
            self.assertFalse(valid_min_cppstd(conanfile, cppstd, True))
