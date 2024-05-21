import platform
import textwrap

import pytest

from conan.test.utils.tools import TestClient

conanfile = textwrap.dedent("""\
[generators]
IntelCC
""")

intelprofile = textwrap.dedent("""\
[settings]
os=%s
arch=x86_64
compiler=intel-cc
compiler.mode=dpcpp
compiler.version=2021.3
compiler.libcxx=libstdc++
build_type=Release

[conf]
tools.intel:installation_path=%s
""")


def get_intel_cc_generator_file(os_, installation_path, filename):
    profile = intelprofile % (os_, installation_path)
    client = TestClient()
    client.save({
        "conanfile.txt": conanfile,
        "intelprofile": profile,
    })
    client.run("install . -pr intelprofile")
    return client.load(filename)


@pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows")
def test_intel_cc_generator_windows():
    os_ = "Windows"
    installation_path = "C:\\Program Files (x86)\\Intel\\oneAPI"
    conanintelsetvars = get_intel_cc_generator_file(os_, installation_path, "conanintelsetvars.bat")
    expected = textwrap.dedent("""\
        @echo off
        call "C:\\Program Files (x86)\\Intel\\oneAPI\\setvars.bat" intel64
        """)
    assert conanintelsetvars == expected


@pytest.mark.skipif(platform.system() != "Linux", reason="Requires Linux")
def test_intel_cc_generator_linux():
    os_ = "Linux"
    installation_path = "/opt/intel/oneapi"
    conanintelsetvars = get_intel_cc_generator_file(os_, installation_path, "conanintelsetvars.sh")
    expected = '. "/opt/intel/oneapi/setvars.sh" intel64'
    assert conanintelsetvars == expected
