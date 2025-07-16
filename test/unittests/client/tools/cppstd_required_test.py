import pytest
from mock import mock

from conan.tools.build import check_max_cppstd, check_min_cppstd, valid_max_cppstd, valid_min_cppstd, \
    valid_min_cstd, valid_max_cstd
from conan.test.utils.mocks import MockSettings, ConanFileMock
from conan.errors import ConanException, ConanInvalidConfiguration


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


class TestUserInput:

    def test_check_cppstd_type(self):
        """ cppstd must be a number
        """
        conanfile = ConanFileMock(MockSettings({}))
        with pytest.raises(ConanException) as raises:
            check_min_cppstd(conanfile, "gnu17", False)
        assert "cppstd parameter must be a number" == str(raises.value)


class TestCheckMinCppStd:

    @pytest.mark.parametrize("cppstd", ["98", "11", "14", "17"])
    def test_check_min_cppstd_from_settings(self, cppstd):
        """ check_min_cppstd must accept cppstd less/equal than cppstd in settings
        """
        conanfile = _create_conanfile("gcc", "9", "Linux", "17", "libstdc++")
        check_min_cppstd(conanfile, cppstd, False)

    @pytest.mark.parametrize("cppstd", ["98", "11", "14"])
    def test_check_min_cppstd_from_outdated_settings(self, cppstd):
        """ check_min_cppstd must raise when cppstd is greater when supported on settings
        """
        conanfile = _create_conanfile("gcc", "9", "Linux", cppstd, "libstdc++")
        with pytest.raises(ConanInvalidConfiguration) as raises:
            check_min_cppstd(conanfile, "17", False)
        assert "Current cppstd ({}) is lower than the required C++ standard (17).".format(cppstd) == str(raises.value)

    @pytest.mark.parametrize("cppstd", ["98", "11", "14", "17"])
    def test_check_min_cppstd_from_settings_with_extension(self, cppstd):
        """ current cppstd in settings must has GNU extension when extensions is enabled
        """
        conanfile = _create_conanfile("gcc", "9", "Linux", "gnu17", "libstdc++")
        check_min_cppstd(conanfile, cppstd, True)

        conanfile.settings.values["compiler.cppstd"] = "17"
        with pytest.raises(ConanException) as raises:
            check_min_cppstd(conanfile, cppstd, True)
        assert "The cppstd GNU extension is required" == str(raises.value)

    def test_check_min_cppstd_unsupported_standard(self):
        """ check_min_cppstd must raise when the compiler does not support a standard
        """
        conanfile = _create_conanfile("gcc", "9", "Linux", "gnu14", "libstdc++")
        with pytest.raises(ConanInvalidConfiguration) as raises:
            check_min_cppstd(conanfile, "42", False)
        assert "Current cppstd (gnu14) is lower than the required C++ standard (42)." == str(raises.value)

    def test_check_min_cppstd_gnu_compiler_extension(self):
        """ Current compiler must support GNU extension on Linux when extensions is required
        """
        conanfile = _create_conanfile("gcc", "9", "Linux", "17", "libstdc++")
        with mock.patch("platform.system", mock.MagicMock(return_value="Linux")):
            with pytest.raises(ConanException) as raises:
                check_min_cppstd(conanfile, "17", True)
            assert "The cppstd GNU extension is required" == str(raises.value)


class TestValidMinCppstd:

    @pytest.mark.parametrize("cppstd", ["98", "11", "14", "17"])
    def test_valid_min_cppstd_from_settings(self, cppstd):
        """ valid_min_cppstd must accept cppstd less/equal than cppstd in settings
        """
        conanfile = _create_conanfile("gcc", "9", "Linux", "17", "libstdc++")
        assert valid_min_cppstd(conanfile, cppstd, False)

    @pytest.mark.parametrize("cppstd", ["98", "11", "14"])
    def test_valid_min_cppstd_from_outdated_settings(self, cppstd):
        """ valid_min_cppstd returns False when cppstd is greater when supported on settings
        """
        conanfile = _create_conanfile("gcc", "9", "Linux", cppstd, "libstdc++")
        assert not valid_min_cppstd(conanfile, "17", False)

    @pytest.mark.parametrize("cppstd", ["98", "11", "14", "17"])
    def test_valid_min_cppstd_from_settings_with_extension(self, cppstd):
        """ valid_min_cppstd must returns True when current cppstd in settings has GNU extension and
            extensions is enabled
        """
        conanfile = _create_conanfile("gcc", "9", "Linux", "gnu17", "libstdc++")
        assert valid_min_cppstd(conanfile, cppstd, True)

        conanfile.settings.values["compiler.cppstd"] = "17"
        assert not valid_min_cppstd(conanfile, cppstd, True)

    def test_valid_min_cppstd_unsupported_standard(self):
        """ valid_min_cppstd must returns False when the compiler does not support a standard
        """
        conanfile = _create_conanfile("gcc", "9", "Linux", "17", "libstdc++")
        assert not valid_min_cppstd(conanfile, "42", False)

    def test_valid_min_cppstd_gnu_compiler_extension(self):
        """ valid_min_cppstd must returns False when current compiler does not support GNU extension
            on Linux and extensions is required
        """
        conanfile = _create_conanfile("gcc", "9", "Linux", "gnu1z", "libstdc++")
        with mock.patch("platform.system", mock.MagicMock(return_value="Linux")):
            assert not valid_min_cppstd(conanfile, "20", True)

    @pytest.mark.parametrize("cppstd", ["98", "11", "14", "17"])
    def test_min_cppstd_mingw_windows(self, cppstd):
        """ GNU extensions HAS effect on Windows when running a cross-building for Linux
        """
        with mock.patch("platform.system", mock.MagicMock(return_value="Windows")):
            conanfile = _create_conanfile("gcc", "9", "Linux", "gnu17", "libstdc++")
            assert valid_min_cppstd(conanfile, cppstd, True)

            conanfile.settings.values["compiler.cppstd"] = "17"
            assert not valid_min_cppstd(conanfile, cppstd, True)


class TestCheckMaxCppStd:

    @pytest.mark.parametrize("cppstd", ["98", "11", "14", "17"])
    def test_check_max_cppstd_from_settings(self, cppstd):
        """ check_max_cppstd must accept cppstd higher/equal than cppstd in settings
        """
        conanfile = _create_conanfile("gcc", "9", "Linux", "98", "libstdc++")
        check_max_cppstd(conanfile, cppstd, False)

    @pytest.mark.parametrize("cppstd", ["11", "14", "17"])
    def test_check_max_cppstd_from_outdated_settings(self, cppstd):
        """ check_max_cppstd must raise when cppstd is higher when supported on settings
        """
        conanfile = _create_conanfile("gcc", "9", "Linux", cppstd, "libstdc++")
        with pytest.raises(ConanInvalidConfiguration) as raises:
            check_max_cppstd(conanfile, "98", False)
        assert "Current cppstd ({}) is higher than the required C++ standard (98).".format(cppstd) == str(raises.value)

    @pytest.mark.parametrize("cppstd", ["98", "11", "14", "17"])
    def test_check_max_cppstd_from_settings_with_extension(self, cppstd):
        """ current cppstd in settings must have GNU extension when extensions is enabled
        """
        conanfile = _create_conanfile("gcc", "9", "Linux", "gnu98", "libstdc++")
        check_max_cppstd(conanfile, cppstd, True)

        conanfile.settings.values["compiler.cppstd"] = "98"
        with pytest.raises(ConanException) as raises:
            check_max_cppstd(conanfile, cppstd, True)
        assert "The cppstd GNU extension is required" == str(raises.value)

    def test_check_max_cppstd_unsupported_standard(self):
        """ check_max_cppstd must raise when the compiler does not support a standard
        """
        conanfile = _create_conanfile("gcc", "9", "Linux", "gnu17", "libstdc++")
        with pytest.raises(ConanInvalidConfiguration) as raises:
            check_max_cppstd(conanfile, "16", False)
        assert "Current cppstd (gnu17) is higher than the required C++ standard (16)." == str(raises.value)

    def test_check_max_cppstd_gnu_compiler_extension(self):
        """ Current compiler must support GNU extension on Linux when extensions is required
        """
        conanfile = _create_conanfile("gcc", "9", "Linux", "17", "libstdc++")
        with mock.patch("platform.system", mock.MagicMock(return_value="Linux")):
            with pytest.raises(ConanException) as raises:
                check_max_cppstd(conanfile, "17", True)
            assert "The cppstd GNU extension is required" == str(raises.value)


class TestValidMaxCppstd:

    @pytest.mark.parametrize("cppstd", ["98", "11", "14", "17"])
    def test_valid_max_cppstd_from_settings(self, cppstd):
        """ valid_max_cppstd must accept cppstd higher/equal than cppstd in settings
        """
        conanfile = _create_conanfile("gcc", "9", "Linux", "98", "libstdc++")
        assert valid_max_cppstd(conanfile, cppstd, False)

    @pytest.mark.parametrize("cppstd", ["11", "14", "17"])
    def test_valid_max_cppstd_from_outdated_settings(self, cppstd):
        """ valid_max_cppstd return False when cppstd is greater when supported on settings
        """
        conanfile = _create_conanfile("gcc", "9", "Linux", cppstd, "libstdc++")
        assert not valid_max_cppstd(conanfile, "98", False)

    @pytest.mark.parametrize("cppstd", ["98", "11", "14", "17"])
    def test_valid_max_cppstd_from_settings_with_extension(self, cppstd):
        """ valid_max_cppstd must return True when current cppstd in settings has GNU extension and
            extensions is enabled
        """
        conanfile = _create_conanfile("gcc", "9", "Linux", "gnu98", "libstdc++")
        assert valid_max_cppstd(conanfile, cppstd, True)

        conanfile.settings.values["compiler.cppstd"] = "98"
        assert not valid_max_cppstd(conanfile, cppstd, True)

    def test_valid_max_cppstd_unsupported_standard(self):
        """ valid_max_cppstd must return False when the compiler does not support a standard
        """
        conanfile = _create_conanfile("gcc", "9", "Linux", "17", "libstdc++")
        assert not valid_max_cppstd(conanfile, "16", False)

    def test_valid_max_cppstd_gnu_compiler_extension(self):
        """ valid_max_cppstd must return False when current compiler does not support GNU extension
            on Linux and extensions is required
        """
        conanfile = _create_conanfile("gcc", "9", "Linux", "gnu17", "libstdc++")
        with mock.patch("platform.system", mock.MagicMock(return_value="Linux")):
            assert not valid_max_cppstd(conanfile, "14", True)

    @pytest.mark.parametrize("cppstd", ["98", "11", "14", "17"])
    def test_max_cppstd_mingw_windows(self, cppstd):
        """ GNU extensions HAS effect on Windows when running a cross-building for Linux
        """
        with mock.patch("platform.system", mock.MagicMock(return_value="Windows")):
            conanfile = _create_conanfile("gcc", "9", "Linux", "gnu98", "libstdc++")
            assert valid_max_cppstd(conanfile, cppstd, True)

            conanfile.settings.values["compiler.cppstd"] = "98"
            assert not valid_max_cppstd(conanfile, cppstd, True)


class TestCstd:

    @pytest.mark.parametrize("compiler, cstd, mincstd, valid",
                             [["gcc",  "99", "99", True],
                              ["gcc",  "gnu99", "99", True],
                              ["gcc", "99", "11", False]
                              ])
    def test_valid_min(self, compiler, cstd, mincstd, valid):
        settings = MockSettings({"arch": "x86_64",
                                 "build_type": "Debug",
                                 "os": "Linux",
                                 "compiler": compiler,
                                 "compiler.cstd": cstd})
        conanfile = ConanFileMock(settings)
        if valid:
            assert valid_min_cstd(conanfile, mincstd, False)
        else:
            assert not valid_min_cstd(conanfile, mincstd, False)

    @pytest.mark.parametrize("compiler, cstd, maxcstd, valid",
                             [["gcc", "99", "11", True],
                              ["gcc", "gnu99", "11", True],
                              ["gcc", "17", "11", False]
                              ])
    def test_valid_max(self, compiler, cstd, maxcstd, valid):
        settings = MockSettings({"arch": "x86_64",
                                 "build_type": "Debug",
                                 "os": "Linux",
                                 "compiler": compiler,
                                 "compiler.cstd": cstd})
        conanfile = ConanFileMock(settings)
        if valid:
            assert valid_max_cstd(conanfile, maxcstd, False)
        else:
            assert not valid_max_cstd(conanfile, maxcstd, False)

    def test_error(self):
        conanfile = ConanFileMock()
        with pytest.raises(ConanException) as e:
            valid_min_cstd(conanfile, "potato")
        assert "cstd parameter must be a number" in str(e.value)
