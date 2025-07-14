import pytest

from conan.tools.build import supported_cstd, check_min_cstd
from conan.errors import ConanException
from conan.test.utils.mocks import MockSettings, ConanFileMock


@pytest.mark.parametrize("compiler,compiler_version,values", [
    ("clang", "2.1", ['99', 'gnu99']),
    ("clang", "5", ['99', 'gnu99', '11', 'gnu11']),
    ("clang", "17", ['99', 'gnu99', '11', 'gnu11', "17", "gnu17"]),
    ("clang", "18", ['99', 'gnu99', '11', 'gnu11',  "17", "gnu17", "23", "gnu23"])
])
def test_supported_cstd_clang(compiler, compiler_version, values):
    settings = MockSettings({"compiler": compiler, "compiler.version": compiler_version})
    conanfile = ConanFileMock(settings)
    sot = supported_cstd(conanfile)
    assert sot == values


def test_supported_cstd_with_specific_values():
    settings = MockSettings({})
    conanfile = ConanFileMock(settings)
    sot = supported_cstd(conanfile, "clang", "5")
    assert sot == ['99', 'gnu99', '11', 'gnu11']


def test_supported_cstd_error():
    settings = MockSettings({})
    conanfile = ConanFileMock(settings)
    with pytest.raises(ConanException) as exc:
        supported_cstd(conanfile)
    assert "Called supported_cstd with no compiler or no compiler.version" in str(exc)


@pytest.mark.parametrize("compiler,compiler_version,values", [
    ("gcc", "4.6", ['99', 'gnu99']),
    ("gcc", "5", ['99', 'gnu99', '11', 'gnu11']),
    ("gcc", "13", ["99", "gnu99", "11", "gnu11", "17", "gnu17"]),
    ("gcc", "14", ["99", "gnu99", "11", "gnu11", "17", "gnu17", "23", "gnu23"])
])
def test_supported_cppstd_gcc(compiler, compiler_version, values):
    settings = MockSettings({"compiler": compiler, "compiler.version": compiler_version})
    conanfile = ConanFileMock(settings)
    sot = supported_cstd(conanfile)
    assert sot == values


@pytest.mark.parametrize("compiler,compiler_version,values", [
    ("msvc", "191", []),
    ("msvc", "193", ['11', '17']),
])
def test_supported_cstd_msvc(compiler, compiler_version, values):
    settings = MockSettings({"compiler": compiler, "compiler.version": compiler_version})
    conanfile = ConanFileMock(settings)
    sot = supported_cstd(conanfile)
    assert sot == values


def test_check_cstd_type():
    """ cppstd must be a number
    """
    conanfile = ConanFileMock(MockSettings({}))
    with pytest.raises(ConanException) as exc:
        check_min_cstd(conanfile, "gnu17", False)

    assert "cstd parameter must be a number", str(exc)
