import unittest
from mock import mock
from parameterized import parameterized

from conans.test.utils.conanfile import MockConanfile, MockSettings
from conans.client.tools import OSInfo
from conans.errors import ConanInvalidConfiguration

from conans.tools import check_min_cppstd, valid_min_cppstd


class UserProneTests(unittest.TestCase):

    def setUp(self):
        self.conanfile = MockConanfile(MockSettings({}))

    @parameterized.expand(["check_min_cppstd", "valid_min_cppstd"])
    def test_check_none_cppstd(self, method):
        """ Cppstd must use a valid number as described in settings.yml
        """
        with self.assertRaises(AssertionError) as asserts:
            eval(method)(self.conanfile, None, False)
        self.assertEqual("Cannot check invalid cppstd version", str(asserts.exception))

    @parameterized.expand(["check_min_cppstd", "valid_min_cppstd"])
    def test_check_none_conanfile(self, method):
        """ conanfile must be a ConanFile object
        """
        with self.assertRaises(AssertionError) as raises:
            eval(method)(None, "17", False)
        self.assertEqual("conanfile must be a ConanFile object", str(raises.exception))


class CheckMinCppStdTests(unittest.TestCase):

    def setUp(self):
        self.conanfile = self._create_conanfile("gcc", "9", "Linux", "17", "libcxx")

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

    @parameterized.expand(["98", "gnu98", "11", "gnu11", "14", "gnu14", "17", "gnu17"])
    def test_check_min_cppstd_from_settings(self, cppstd):
        """ check_min_cppstd must accept cppstd less/equal than cppstd in settings
        """
        check_min_cppstd(self.conanfile, cppstd, False)

    @parameterized.expand(["98", "gnu98", "11", "gnu11", "14", "gnu14"])
    def test_check_min_cppstd_from_outdated_settings(self, cppstd):
        """ check_min_cppstd must raise when cppstd is greater when supported on settings
        """
        self.conanfile.settings.values["compiler.cppstd"] = cppstd
        with self.assertRaises(ConanInvalidConfiguration) as raises:
            check_min_cppstd(self.conanfile, "17", False)
        self.assertEqual("Current cppstd ({}) is lower than required c++ standard " 
                         "(17).".format(cppstd), str(raises.exception))

    @parameterized.expand(["98", "gnu98", "11", "gnu11", "14", "gnu14", "17", "gnu17"])
    def test_check_min_cppstd_from_settings_with_extension(self, cppstd):
        """ current cppstd in settings must has GNU extension when extensions is enabled
        """
        with mock.patch("platform.system", mock.MagicMock(return_value="Linux")):
            with mock.patch.object(OSInfo, '_get_linux_distro_info'):
                self.conanfile.settings.values["compiler.cppstd"] = "gnu17"
                check_min_cppstd(self.conanfile, cppstd, True)

                self.conanfile.settings.values["compiler.cppstd"] = "17"
                with self.assertRaises(ConanInvalidConfiguration) as raises:
                    check_min_cppstd(self.conanfile, cppstd, True)
                self.assertEqual("Current cppstd (17) does not have GNU extensions, which is "
                                 "required on Linux platform.", str(raises.exception))

    @parameterized.expand(["98", "gnu98", "11", "gnu11", "14", "gnu14", "17", "gnu17"])
    def test_check_min_cppstd_from_settings_with_extension_windows(self, cppstd):
        """ GNU extensions has no effect on Windows for check_min_cppstd
        """
        with mock.patch("platform.system", mock.MagicMock(return_value="Windows")):
            self.conanfile.settings.values["compiler.cppstd"] = "gnu17"
            check_min_cppstd(self.conanfile, cppstd, True)

            self.conanfile.settings.values["compiler.cppstd"] = "17"
            check_min_cppstd(self.conanfile, cppstd, True)

    def test_check_min_cppstd_unsupported_standard(self):
        """ check_min_cppstd must raise when the compiler does not support a standard
        """
        del self.conanfile.settings.values["compiler.cppstd"]
        with self.assertRaises(ConanInvalidConfiguration) as raises:
            check_min_cppstd(self.conanfile, "42", False)
        self.assertEqual("Current compiler does not support the required c++ standard (42).",
                         str(raises.exception))

    def test_check_min_cppstd_gnu_compiler_extension(self):
        """ Current compiler must support GNU extension on Linux when extensions is required
        """
        del self.conanfile.settings.values["compiler.cppstd"]
        with mock.patch("platform.system", mock.MagicMock(return_value="Linux")):
            with mock.patch.object(OSInfo, '_get_linux_distro_info'):
                with mock.patch("conans.client.tools.settings.cppstd_flag", return_value="42"):
                    with self.assertRaises(ConanInvalidConfiguration) as raises:
                        check_min_cppstd(self.conanfile, "gnu42", True)
                    self.assertEqual("Current compiler does not support GNU extensions.",
                                     str(raises.exception))


class ValidMinCppstdTests(unittest.TestCase):

    def setUp(self):
        self.conanfile = self._create_conanfile("gcc", "9", "Linux", "17", "libcxx")

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

    @parameterized.expand(["98", "gnu98", "11", "gnu11", "14", "gnu14", "17", "gnu17"])
    def test_valid_min_cppstd_from_settings(self, cppstd):
        """ valid_min_cppstd must accept cppstd less/equal than cppstd in settings
        """
        self.assertTrue(valid_min_cppstd(self.conanfile, cppstd, False))

    @parameterized.expand(["98", "gnu98", "11", "gnu11", "14", "gnu14"])
    def test_valid_min_cppstd_from_outdated_settings(self, cppstd):
        """ valid_min_cppstd returns False when cppstd is greater when supported on settings
        """
        self.conanfile.settings.values["compiler.cppstd"] = cppstd
        self.assertFalse(valid_min_cppstd(self.conanfile, "17", False))

    @parameterized.expand(["98", "gnu98", "11", "gnu11", "14", "gnu14", "17", "gnu17"])
    def test_valid_min_cppstd_from_settings_with_extension(self, cppstd):
        """ valid_min_cppstd must returns True when current cppstd in settings has GNU extension and
            extensions is enabled
        """
        with mock.patch("platform.system", mock.MagicMock(return_value="Linux")):
            with mock.patch.object(OSInfo, '_get_linux_distro_info'):
                self.conanfile.settings.values["compiler.cppstd"] = "gnu17"
                self.assertTrue(valid_min_cppstd(self.conanfile, cppstd, True))

                self.conanfile.settings.values["compiler.cppstd"] = "17"
                self.assertFalse(valid_min_cppstd(self.conanfile, cppstd, True))

    @parameterized.expand(["98", "gnu98", "11", "gnu11", "14", "gnu14", "17", "gnu17"])
    def test_valid_min_cppstd_from_settings_with_extension_windows(self, cppstd):
        """ GNU extensions has no effect on Windows for valid_min_cppstd
        """
        with mock.patch("platform.system", mock.MagicMock(return_value="Windows")):
            self.conanfile.settings.values["compiler.cppstd"] = "gnu17"
            self.assertTrue(valid_min_cppstd(self.conanfile, cppstd, True))

            self.conanfile.settings.values["compiler.cppstd"] = "17"
            self.assertTrue(valid_min_cppstd(self.conanfile, cppstd, True))

    def test_valid_min_cppstd_unsupported_standard(self):
        """ valid_min_cppstd must returns False when the compiler does not support a standard
        """
        del self.conanfile.settings.values["compiler.cppstd"]
        self.assertFalse(valid_min_cppstd(self.conanfile, "42", False))

    def test_valid_min_cppstd_gnu_compiler_extension(self):
        """ valid_min_cppstd must returns False when current compiler does not support GNU extension
            on Linux and extensions is required
        """
        del self.conanfile.settings.values["compiler.cppstd"]
        with mock.patch("platform.system", mock.MagicMock(return_value="Linux")):
            with mock.patch.object(OSInfo, '_get_linux_distro_info'):
                with mock.patch("conans.client.tools.settings.cppstd_flag", return_value="42"):
                    self.assertFalse(valid_min_cppstd(self.conanfile, "gnu42", True))
