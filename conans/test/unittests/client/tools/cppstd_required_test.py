import unittest
from mock import mock
from parameterized import parameterized

from conans.test.utils.conanfile import MockConanfile, MockSettings
from conans.client.tools import OSInfo
from conans.errors import ConanInvalidConfiguration

from conans.tools import check_min_cppstd, valid_min_cppstd


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

    def test_check_none_cppstd(self):
        """ Cppstd must use a valid number as described in settings.yml
        """
        with self.assertRaises(AssertionError) as asserts:
            check_min_cppstd(self.conanfile, None, False)
        self.assertEqual("Cannot check invalid cppstd version", str(asserts.exception))

    def test_check_none_conanfile(self):
        """ conanfile must be a ConanFile object
        """
        with self.assertRaises(AssertionError) as raises:
            check_min_cppstd(None, "17", False)
        self.assertEqual("conanfile must be a ConanFile object", str(raises.exception))

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
        """ GNU extensions has no effect on Windows
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

    @mock.patch("conans.client.build.cppstd_flags.cppstd_flag", return_value="42")
    def test_check_min_cppstd_gnu_compiler_extension(self, _):
        """ Current compiler must support GNU extension on Linux when extensions is required
        """
        del self.conanfile.settings.values["compiler.cppstd"]
        with mock.patch("platform.system", mock.MagicMock(return_value="Linux")):
            with mock.patch.object(OSInfo, '_get_linux_distro_info'):
                with self.assertRaises(ConanInvalidConfiguration) as raises:
                    check_min_cppstd(self.conanfile, "gnu42", True)
                self.assertEqual("Current compiler does not support GNU extensions.",
                                 str(raises.exception))
