import pytest

from conan.tools.build import supported_cppstd
from conans.errors import ConanException
from conans.test.utils.mocks import MockSettings, MockConanfile


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
    conanfile = MockConanfile(settings)
    sot = supported_cppstd(conanfile)
    assert sot == values


def test_supported_cppstd_with_specific_values():
    settings = MockSettings({})
    conanfile = MockConanfile(settings)
    sot = supported_cppstd(conanfile, "clang", "3.1")
    assert sot == ['98', 'gnu98', '11', 'gnu11']


def test_supported_cppstd_error():
    settings = MockSettings({})
    conanfile = MockConanfile(settings)
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
    conanfile = MockConanfile(settings)
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
])
def test_supported_cppstd_apple_clang(compiler, compiler_version, values):
    settings = MockSettings({"compiler": compiler, "compiler.version": compiler_version})
    conanfile = MockConanfile(settings)
    sot = supported_cppstd(conanfile)
    assert sot == values


@pytest.mark.parametrize("compiler,compiler_version,values", [
    ("msvc", "180", []),
    ("msvc", "190", ['14', '17']),
    ("msvc", "191", ['14', '17', '20']),
    ("msvc", "193", ['14', '17', '20', '23']),
])
def test_supported_cppstd_msvc(compiler, compiler_version, values):
    settings = MockSettings({"compiler": compiler, "compiler.version": compiler_version})
    conanfile = MockConanfile(settings)
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
    conanfile = MockConanfile(settings)
    sot = supported_cppstd(conanfile)
    assert sot == values
