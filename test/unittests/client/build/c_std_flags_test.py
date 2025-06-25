import unittest

from conan.internal.api.detect.detect_api import default_cstd
from conan.tools.build.flags import cstd_flag
from conan.internal.model.version import Version
from conan.test.utils.mocks import MockSettings, ConanFileMock


def _make_cstd_flag(compiler, compiler_version, cstd=None):
    conanfile = ConanFileMock()
    conanfile.settings = MockSettings({"compiler": compiler,
                                       "compiler.version": compiler_version,
                                       "compiler.cstd": cstd})
    return cstd_flag(conanfile)


def _make_cstd_default(compiler, compiler_version):
    return default_cstd(compiler, Version(compiler_version))


def test_gcc_cstd_defaults():
    assert _make_cstd_default("gcc", "4")== "gnu99"
    assert _make_cstd_default("gcc", "5")== "gnu11"
    assert _make_cstd_default("gcc", "6")== "gnu11"
    assert _make_cstd_default("gcc", "6.1")== "gnu11"
    assert _make_cstd_default("gcc", "7.3")== "gnu11"
    assert _make_cstd_default("gcc", "8.1")== "gnu17"
    assert _make_cstd_default("gcc", "11")== "gnu17"
    assert _make_cstd_default("gcc", "11.1")== "gnu17"
    assert _make_cstd_default("gcc", "15.1")== "gnu23"

def test_clang_cstd_defaults():
    assert _make_cstd_default("clang", "2")== "gnu99"
    assert _make_cstd_default("clang", "2.1")== "gnu99"
    assert _make_cstd_default("clang", "3.0")== "gnu99"
    assert _make_cstd_default("clang", "3.1")== "gnu99"
    assert _make_cstd_default("clang", "3.4")== "gnu99"
    assert _make_cstd_default("clang", "3.5")== "gnu99"
    assert _make_cstd_default("clang", "5")== "gnu11"
    assert _make_cstd_default("clang", "5.1")== "gnu11"
    assert _make_cstd_default("clang", "6")== "gnu11"
    assert _make_cstd_default("clang", "7")== "gnu11"
    assert _make_cstd_default("clang", "8")== "gnu11"
    assert _make_cstd_default("clang", "9")== "gnu11"
    assert _make_cstd_default("clang", "10")== "gnu11"
    assert _make_cstd_default("clang", "11")== "gnu17"
    assert _make_cstd_default("clang", "12")== "gnu17"
    assert _make_cstd_default("clang", "13")== "gnu17"
    assert _make_cstd_default("clang", "14")== "gnu17"
    assert _make_cstd_default("clang", "15")== "gnu17"
    assert _make_cstd_default("clang", "16")== "gnu17"
    assert _make_cstd_default("clang", "17")== "gnu17"
    assert _make_cstd_default("clang", "18")== "gnu17"
    assert _make_cstd_default("clang", "19")== "gnu17"
    assert _make_cstd_default("clang", "20"), "gnu17"


def test_apple_clang_cppstd_defaults():
    assert _make_cstd_default("apple-clang", "9") == "gnu99"
    assert _make_cstd_default("apple-clang", "10") == "gnu11"
    assert _make_cstd_default("apple-clang", "11") == "gnu11"
    assert _make_cstd_default("apple-clang", "12") == "gnu17"
    assert _make_cstd_default("apple-clang", "13") == "gnu17"
    assert _make_cstd_default("apple-clang", "14") == "gnu17"
    assert _make_cstd_default("apple-clang", "15") == "gnu17"
