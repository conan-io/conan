import pytest

from conan.tools.gnu.get_gnu_triplet import _get_gnu_triplet, _get_gnu_os, _get_gnu_arch
from conans.errors import ConanException


@pytest.mark.parametrize("os_, arch, compiler, expected", [
    ["Linux", "x86", None, "i686-linux-gnu"],
    ["Linux", "x86_64", None, "x86_64-linux-gnu"],
    ["Linux", "armv6", None, "arm-linux-gnueabi"],
    ["Linux", "sparc", None, "sparc-linux-gnu"],
    ["Linux", "sparcv9", None, "sparc64-linux-gnu"],
    ["Linux", "mips", None, "mips-linux-gnu"],
    ["Linux", "mips64", None, "mips64-linux-gnu"],
    ["Linux", "ppc32", None, "powerpc-linux-gnu"],
    ["Linux", "ppc64", None, "powerpc64-linux-gnu"],
    ["Linux", "ppc64le", None, "powerpc64le-linux-gnu"],
    ["Linux", "armv5te", None, "arm-linux-gnueabi"],
    ["Linux", "arm_whatever", None, "arm-linux-gnueabi"],
    ["Linux", "armv7hf", None, "arm-linux-gnueabihf"],
    ["Linux", "armv6", None, "arm-linux-gnueabi"],
    ["Linux", "armv7", None, "arm-linux-gnueabi"],
    ["Linux", "armv8_32", None, "aarch64-linux-gnu_ilp32"],
    ["Linux", "armv5el", None, "arm-linux-gnueabi"],
    ["Linux", "armv5hf", None, "arm-linux-gnueabihf"],
    ["Linux", "s390", None, "s390-ibm-linux-gnu"],
    ["Linux", "s390x", None, "s390x-ibm-linux-gnu"],
    ["Android", "x86", None, "i686-linux-android"],
    ["Android", "x86_64", None, "x86_64-linux-android"],
    ["Android", "armv6", None, "arm-linux-androideabi"],
    ["Android", "armv7", None, "arm-linux-androideabi"],
    ["Android", "armv7hf", None, "arm-linux-androideabi"],
    ["Android", "armv8", None, "aarch64-linux-android"],
    ["Windows", "x86", "msvc", "i686-unknown-windows"],
    ["Windows", "x86_64", "msvc", "x86_64-unknown-windows"],
    ["Windows", "armv8", "msvc", "aarch64-unknown-windows"],
    ["Windows", "x86", "gcc", "i686-w64-mingw32"],
    ["Windows", "x86_64", "gcc", "x86_64-w64-mingw32"],
    ["Darwin", "x86_64", None, "x86_64-apple-darwin"],
    ["Macos", "x86", None, "i686-apple-darwin"],
    ["iOS", "armv7", None, "arm-apple-ios"],
    ["iOS", "x86", None, "i686-apple-ios"],
    ["iOS", "x86_64", None, "x86_64-apple-ios"],
    ["watchOS", "armv7k", None, "arm-apple-watchos"],
    ["watchOS", "armv8_32", None, "aarch64-apple-watchos"],
    ["watchOS", "x86", None, "i686-apple-watchos"],
    ["watchOS", "x86_64", None, "x86_64-apple-watchos"],
    ["tvOS", "armv8", None, "aarch64-apple-tvos"],
    ["tvOS", "armv8.3", None, "aarch64-apple-tvos"],
    ["tvOS", "x86", None, "i686-apple-tvos"],
    ["tvOS", "x86_64", None, "x86_64-apple-tvos"],
    ["Emscripten", "asm.js", None, "asmjs-local-emscripten"],
    ["Emscripten", "wasm", None, "wasm32-local-emscripten"],
    ["AIX", "ppc32", None, "rs6000-ibm-aix"],
    ["AIX", "ppc64", None, "powerpc-ibm-aix"],
    ["Neutrino", "armv7", None, "arm-nto-qnx"],
    ["Neutrino", "armv8", None, "aarch64-nto-qnx"],
    ["Neutrino", "sh4le", None, "sh4-nto-qnx"],
    ["Neutrino", "ppc32be", None, "powerpcbe-nto-qnx"],
    ["Linux", "e2k-v2", None, "e2k-unknown-linux-gnu"],
    ["Linux", "e2k-v3", None, "e2k-unknown-linux-gnu"],
    ["Linux", "e2k-v4", None, "e2k-unknown-linux-gnu"],
    ["Linux", "e2k-v5", None, "e2k-unknown-linux-gnu"],
    ["Linux", "e2k-v6", None, "e2k-unknown-linux-gnu"],
    ["Linux", "e2k-v7", None, "e2k-unknown-linux-gnu"],
    ["Linux", "riscv32", None, "riscv32-linux-gnu"],
    ["Linux", "riscv64", None, "riscv64-linux-gnu"],
])
def test_get_gnu_triplet(os_, arch, compiler, expected):
    info = _get_gnu_triplet(os_, arch, compiler)
    assert info["triplet"] == expected
    assert info["machine"] == _get_gnu_arch(os_, arch)
    assert info["system"] == _get_gnu_os(os_, arch, compiler)


def test_get_gnu_triplet_on_windows_without_compiler():
    with pytest.raises(ConanException):
        _get_gnu_triplet("Windows", "x86")
