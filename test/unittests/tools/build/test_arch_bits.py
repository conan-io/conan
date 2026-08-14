import pytest

from conan.tools.build import architecture_bits
from conan.test.utils.mocks import MockSettings, ConanFileMock


@pytest.mark.parametrize("arch,expected", [
    ("x86_64", "64"),
    ("ppc64le", "64"),
    ("ppc64", "64"),
    ("armv8", "64"),
    ("armv8.3", "64"),
    ("arm64ec", "64"),
    ("sparcv9", "64"),
    ("mips64", "64"),
    ("s390x", "64"),
    ("wasm64", "64"),
    ("e2k-v2", "64"),
    ("e2k-v3", "64"),
    ("e2k-v4", "64"),
    ("e2k-v5", "64"),
    ("e2k-v6", "64"),
    ("e2k-v7", "64"),
    ("riscv64", "64"),
    ("x86", "32"),
    ("ppc32be", "32"),
    ("ppc32", "32"),
    ("armv4", "32"),
    ("armv4i", "32"),
    ("armv5el", "32"),
    ("armv5hf", "32"),
    ("armv6", "32"),
    ("armv7", "32"),
    ("armv7hf", "32"),
    ("armv7s", "32"),
    ("armv7k", "32"),
    ("armv8_32", "32"),
    ("sparc", "32"),
    ("mips", "32"),
    ("avr", "32"),
    ("s390", "32"),
    ("asm.js", "32"),
    ("wasm", "32"),
    ("sh4le", "32"),
    ("riscv32", "32"),
    ("xtensalx6", "32"),
    ("xtensalx106", "32"),
    ("xtensalx7", "32"),
    ("tc131", "32"),
    ("tc16", "32"),
    ("tc161", "32"),
    ("tc162", "32"),
    ("tc18", "32"),
    ("unknown_arch", None),
    ("epictetus", None),
    ("", None),
    (None, None),
])
def test_architecture_bits(arch, expected):
    settings = MockSettings({"arch": arch})
    conanfile = ConanFileMock(settings)
    sot = architecture_bits(conanfile)
    assert sot == expected


def test_architecture_bits_missing_setting():
    settings = MockSettings({})
    conanfile = ConanFileMock(settings)
    sot = architecture_bits(conanfile)
    assert sot is None
