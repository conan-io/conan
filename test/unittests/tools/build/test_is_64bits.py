import pytest

from conan.tools.build import is_64_bit_architecture
from conan.test.utils.mocks import MockSettings, ConanFileMock


@pytest.mark.parametrize("arch,expected", [
    ("x86_64", True),
    ("ppc64le", True),
    ("ppc64", True),
    ("armv8", True),
    ("armv8.3", True),
    ("arm64ec", True),
    ("sparcv9", True),
    ("mips64", True),
    ("s390x", True),
    ("wasm64", True),
    ("e2k-v2", True),
    ("e2k-v3", True),
    ("e2k-v4", True),
    ("e2k-v5", True),
    ("e2k-v6", True),
    ("e2k-v7", True),
    ("riscv64", True),
    ("x86", False),
    ("ppc32be", False),
    ("ppc32", False),
    ("armv4", False),
    ("armv4i", False),
    ("armv5el", False),
    ("armv5hf", False),
    ("armv6", False),
    ("armv7", False),
    ("armv7hf", False),
    ("armv7s", False),
    ("armv7k", False),
    ("armv8_32", False),
    ("sparc", False),
    ("mips", False),
    ("avr", False),
    ("s390", False),
    ("asm.js", False),
    ("wasm", False),
    ("sh4le", False),
    ("riscv32", False),
    ("xtensalx6", False),
    ("xtensalx106", False),
    ("xtensalx7", False),
    ("tc131", False),
    ("tc16", False),
    ("tc161", False),
    ("tc162", False),
    ("tc18", False),
    ("unknown_arch", None),
    ("epictetus", None),
    ("", None),
    (None, None),
])
def test_is_64_bit_architecture(arch, expected):
    settings = MockSettings({"arch": arch})
    conanfile = ConanFileMock(settings)
    sot = is_64_bit_architecture(conanfile)
    assert sot == expected


def test_is_64_bit_architecture_missing_setting():
    settings = MockSettings({})
    conanfile = ConanFileMock(settings)
    sot = is_64_bit_architecture(conanfile)
    assert sot is None
