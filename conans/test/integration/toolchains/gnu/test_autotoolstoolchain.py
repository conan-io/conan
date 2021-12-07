import textwrap

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_cross_build():
    windows_profile = textwrap.dedent("""
        [settings]
        os=Windows
        arch=x86_64
        compiler=gcc
        compiler.version=6
        compiler.libcxx=libstdc++11
        build_type=Release
        """)
    rpi_profile = textwrap.dedent("""
        [settings]
        os=Linux
        arch=x86_64
        """)

    client = TestClient(path_with_spaces=False)

    conanfile = GenConanfile().with_settings("os", "arch", "compiler", "build_type")\
        .with_generator("AutotoolsToolchain")
    client.save({"conanfile.py": conanfile,
                "rpi": rpi_profile,
                "windows": windows_profile})
    client.run("install . --profile:build=rpi --profile:host=windows")
    toolchain = client.load("conanautotoolstoolchain.sh")

    assert "export CPPFLAGS=\"$CPPFLAGS -DNDEBUG\"" in toolchain
    assert "export CXXFLAGS=\"$CXXFLAGS -m64 -O3 -s\"" in toolchain
