import pytest

from conan.internal.api.detect_api import detect_cppstd
from conan.tools.build import supported_cppstd, check_min_cppstd, valid_min_cppstd
from conans.errors import ConanException, ConanInvalidConfiguration
from conans.model.version import Version
from conan.test.utils.mocks import MockSettings, ConanFileMock


@pytest.mark.parametrize("compiler,compiler_version,values", [
    ("clang", "2.0", []),
    ("clang", "2.1", ['98', 'gnu98', '11', 'gnu11']),
    ("clang", "2.2", ['98', 'gnu98', '11', 'gnu11']),
    ("clang", "3.1", ['98', 'gnu98', '11', 'gnu11']),
    ("clang", "3.4", ['98', 'gnu98', '11', 'gnu11', "14", "gnu14"]),
    ("clang", "3.5", ['98', 'gnu98', '11', 'gnu11', "14", "gnu14", "17", "gnu17"]),
    ("clang", "4.9", ['98', 'gnu98', '11', 'gnu11', "14", "gnu14", "17", "gnu17"]),
    ("clang", "5", ['98', 'gnu98', '11', 'gnu11', "14", "gnu14", "17", "gnu17"]),
    ("clang", "6", ['98', 'gnu98', '11', 'gnu11', "14", "gnu14", "17", "gnu17", "20", "gnu20"]),
    ("clang", "12", ['98', 'gnu98', '11', 'gnu11', "14", "gnu14", "17", "gnu17", "20",
                     "gnu20", "23", "gnu23"])
])
def test_supported_cppstd_clang(compiler, compiler_version, values):
    settings = MockSettings({"compiler": compiler, "compiler.version": compiler_version})
    conanfile = ConanFileMock(settings)
    sot = supported_cppstd(conanfile)
    assert sot == values


@pytest.mark.parametrize("compiler,compiler_version,result", [
    ("gcc", "5", 'gnu98'),
    ("gcc", "8", "gnu14"),
    ("gcc", "12", "gnu17"),
    ("msvc", "190", "14"),
    ("apple-clang", "10.0", "gnu98"),
    # We diverge from the default cppstd for apple-clang >= 11
    ("apple-clang", "12.0", "gnu17"),
    ("clang", "4", "gnu98"),
    ("clang", "6", "gnu14"),
    ("clang", "17", "gnu17")
])
def test_detected_cppstd(compiler, compiler_version, result):
    sot = detect_cppstd(compiler, Version(compiler_version))
    assert sot == result


def test_supported_cppstd_with_specific_values():
    settings = MockSettings({})
    conanfile = ConanFileMock(settings)
    sot = supported_cppstd(conanfile, "clang", "3.1")
    assert sot == ['98', 'gnu98', '11', 'gnu11']


def test_supported_cppstd_error():
    settings = MockSettings({})
    conanfile = ConanFileMock(settings)
    with pytest.raises(ConanException) as exc:
        supported_cppstd(conanfile)
    assert "Called supported_cppstd with no compiler or no compiler.version" in str(exc)


@pytest.mark.parametrize("compiler,compiler_version,values", [
    ("gcc", "2.0", []),
    ("gcc", "3.4", ['98', 'gnu98']),
    ("gcc", "4.2", ['98', 'gnu98']),
    ("gcc", "4.3", ['98', 'gnu98', '11', 'gnu11']),
    ("gcc", "4.8", ['98', 'gnu98', '11', 'gnu11', "14", "gnu14"]),
    ("gcc", "5", ['98', 'gnu98', '11', 'gnu11', "14", "gnu14", "17", "gnu17"]),
    ("gcc", "8", ['98', 'gnu98', '11', 'gnu11', "14", "gnu14", "17", "gnu17", "20", "gnu20"]),
    ("gcc", "11", ['98', 'gnu98', '11', 'gnu11', "14", "gnu14", "17", "gnu17", "20", "gnu20",
                   "23", "gnu23"])
])
def test_supported_cppstd_gcc(compiler, compiler_version, values):
    settings = MockSettings({"compiler": compiler, "compiler.version": compiler_version})
    conanfile = ConanFileMock(settings)
    sot = supported_cppstd(conanfile)
    assert sot == values


@pytest.mark.parametrize("compiler,compiler_version,values", [
    ("apple-clang", "3.9", []),
    ("apple-clang", "4.0", ['98', 'gnu98', '11', 'gnu11']),
    ("apple-clang", "5.0", ['98', 'gnu98', '11', 'gnu11']),
    ("apple-clang", "5.1", ['98', 'gnu98', '11', 'gnu11', "14", "gnu14"]),
    ("apple-clang", "6.1", ['98', 'gnu98', '11', 'gnu11', "14", "gnu14", "17", "gnu17"]),
    ("apple-clang", "9.5", ['98', 'gnu98', '11', 'gnu11', "14", "gnu14", "17", "gnu17"]),
    ("apple-clang", "10", ['98', 'gnu98', '11', 'gnu11', "14", "gnu14", "17", "gnu17", "20",
                           "gnu20"]),
    ("apple-clang", "13", ['98', 'gnu98', '11', 'gnu11', "14", "gnu14", "17", "gnu17", "20",
                           "gnu20", "23", "gnu23"]),
])
def test_supported_cppstd_apple_clang(compiler, compiler_version, values):
    settings = MockSettings({"compiler": compiler, "compiler.version": compiler_version})
    conanfile = ConanFileMock(settings)
    sot = supported_cppstd(conanfile)
    assert sot == values


@pytest.mark.parametrize("compiler,compiler_version,values", [
    ("msvc", "180", []),
    ("msvc", "190", ['14']),
    ("msvc", "191", ['14', '17']),
    ("msvc", "192", ['14', '17', '20']),
    ("msvc", "193", ['14', '17', '20', '23']),
])
def test_supported_cppstd_msvc(compiler, compiler_version, values):
    settings = MockSettings({"compiler": compiler, "compiler.version": compiler_version})
    conanfile = ConanFileMock(settings)
    sot = supported_cppstd(conanfile)
    assert sot == values


@pytest.mark.parametrize("compiler,compiler_version,values", [
    ("mcst-lcc", "1.20", ['98', 'gnu98']),
    ("mcst-lcc", "1.21", ['98', 'gnu98', '11', 'gnu11', "14", "gnu14"]),
    ("mcst-lcc", "1.23", ['98', 'gnu98', '11', 'gnu11', "14", "gnu14"]),
    ("mcst-lcc", "1.24", ['98', 'gnu98', '11', 'gnu11', "14", "gnu14", "17", "gnu17"]),
    ("mcst-lcc", "1.25", ['98', 'gnu98', '11', 'gnu11', "14", "gnu14", "17", "gnu17", "20", "gnu20"])
])
def test_supported_cppstd_mcst(compiler, compiler_version, values):
    settings = MockSettings({"compiler": compiler, "compiler.version": compiler_version})
    conanfile = ConanFileMock(settings)
    sot = supported_cppstd(conanfile)
    assert sot == values


@pytest.mark.parametrize("compiler,compiler_version,values", [
    ("qcc", "4.4", ['98', 'gnu98']),
    ("qcc", "5.4", ['98', 'gnu98', '11', 'gnu11', "14", "gnu14", "17", "gnu17"]),
    ("qcc", "8.3", ['98', 'gnu98', '11', 'gnu11', "14", "gnu14", "17", "gnu17"]),
])
def test_supported_cppstd_qcc(compiler, compiler_version, values):
    settings = MockSettings({"compiler": compiler, "compiler.version": compiler_version})
    conanfile = ConanFileMock(settings)
    sot = supported_cppstd(conanfile)
    assert sot == values


def test_check_cppstd_type():
    """ cppstd must be a number
    """
    conanfile = ConanFileMock(MockSettings({}))
    with pytest.raises(ConanException) as exc:
        check_min_cppstd(conanfile, "gnu17", False)

    assert "cppstd parameter must be a number", str(exc)


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


@pytest.mark.parametrize("cppstd", ["98", "11", "14", "17"])
def test_check_min_cppstd_from_settings(cppstd):
    """ check_min_cppstd must accept cppstd less/equal than cppstd in settings
    """
    conanfile = _create_conanfile("gcc", "9", "Linux", "17", "libstdc++")
    check_min_cppstd(conanfile, cppstd, False)


@pytest.mark.parametrize("cppstd", ["98", "11", "14"])
def test_check_min_cppstd_from_outdated_settings(cppstd):
    """ check_min_cppstd must raise when cppstd is greater when supported on settings
    """
    conanfile = _create_conanfile("gcc", "9", "Linux", cppstd, "libstdc++")
    with pytest.raises(ConanInvalidConfiguration) as exc:
        check_min_cppstd(conanfile, "17", False)
    assert "Current cppstd ({}) is lower than the required C++ standard (17)." \
           "".format(cppstd) == str(exc.value)


@pytest.mark.parametrize("cppstd", ["98", "11", "14", "17"])
def test_check_min_cppstd_from_settings_with_extension(cppstd):
    """ current cppstd in settings must has GNU extension when extensions is enabled
    """
    conanfile = _create_conanfile("gcc", "9", "Linux", "gnu17", "libstdc++")
    check_min_cppstd(conanfile, cppstd, True)

    conanfile.settings.values["compiler.cppstd"] = "17"
    with pytest.raises(ConanException) as raises:
        check_min_cppstd(conanfile, cppstd, True)
    assert "The cppstd GNU extension is required" == str(raises.value)


@pytest.mark.parametrize("cppstd", ["98", "11", "14", "17"])
def test_valid_min_cppstd_from_settings(cppstd):
    """ valid_min_cppstd must accept cppstd less/equal than cppstd in settings
    """
    conanfile = _create_conanfile("gcc", "9", "Linux", "17", "libstdc++")
    assert valid_min_cppstd(conanfile, cppstd, False)


@pytest.mark.parametrize("cppstd", ["98", "11", "14"])
def test_valid_min_cppstd_from_outdated_settings(cppstd):
    """ valid_min_cppstd returns False when cppstd is greater when supported on settings
    """
    conanfile = _create_conanfile("gcc", "9", "Linux", cppstd, "libstdc++")
    assert not valid_min_cppstd(conanfile, "17", False)


@pytest.mark.parametrize("cppstd", ["98", "11", "14", "17"])
def test_valid_min_cppstd_from_settings_with_extension(cppstd):
    """ valid_min_cppstd must returns True when current cppstd in settings has GNU extension and
        extensions is enabled
    """
    conanfile = _create_conanfile("gcc", "9", "Linux", "gnu17", "libstdc++")
    assert valid_min_cppstd(conanfile, cppstd, True)

    conanfile.settings.values["compiler.cppstd"] = "17"
    assert not valid_min_cppstd(conanfile, cppstd, True)


def test_valid_min_cppstd_unsupported_standard():
    """ valid_min_cppstd must returns False when the compiler does not support a standard
    """
    conanfile = _create_conanfile("gcc", "9", "Linux", None, "libstdc++")
    assert not valid_min_cppstd(conanfile, "42", False)
