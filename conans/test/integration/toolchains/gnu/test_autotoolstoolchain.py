import platform
import textwrap

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_extra_flags_via_conf():
    profile = textwrap.dedent("""
        [settings]
        os=Linux
        compiler=gcc
        compiler.version=6
        compiler.libcxx=libstdc++11
        arch=armv8
        build_type=Release

        [conf]
        tools.build:cxxflags=["--flag1", "--flag2"]
        tools.build:cflags+=["--flag3", "--flag4"]
        tools.build:ldflags+=["--flag5", "--flag6"]
        tools.build:cppflags+=["DEF1", "DEF2"]
        """)
    client = TestClient()
    conanfile = GenConanfile().with_settings("os", "arch", "compiler", "build_type")\
        .with_generator("AutotoolsToolchain")
    client.save({"conanfile.py": conanfile,
                "profile": profile})
    client.run("install . --profile:build=profile --profile:host=profile")
    toolchain = client.load("conanautotoolstoolchain{}".format('.sh' if platform.system() != "Windows" else '.bat'))
    assert 'export CPPFLAGS="$CPPFLAGS -DNDEBUG -DDEF1 -DDEF2"' in toolchain
    assert 'export CXXFLAGS="$CXXFLAGS -O3 -s --flag1 --flag2"' in toolchain
    assert 'export CFLAGS="$CFLAGS -O3 -s --flag3 --flag4"' in toolchain
    assert 'export LDFLAGS="$LDFLAGS --flag5 --flag6"' in toolchain
