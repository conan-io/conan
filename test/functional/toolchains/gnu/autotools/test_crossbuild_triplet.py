import platform
import pytest
import textwrap

from conan.test.utils.tools import TestClient

@pytest.mark.skipif(platform.system() not in  ["Darwin", "Linux"], reason="Autotools on Linux or macOS")
def test_crossbuild_triplet_from_conf():

    settings_yml = textwrap.dedent("""
        os:
            Linux:
            Windows:
        arch: [x86_64, hexagon]
        compiler:
            gcc:
                version: ["10", "11"]
                libcxx: [libstdc++11]
        build_type: [None, Debug, Release]
        """)

    host_profile = textwrap.dedent("""
        [settings]
        os=Linux
        arch=hexagon
        compiler=gcc
        compiler.version=10
        compiler.libcxx=libstdc++11
        build_type=Release
        [conf]
        tools.gnu:host_triplet=hexagon-acme-linux-gnu
    """)

    build_profile = textwrap.dedent("""
        [settings]
        os=Linux
        arch=x86_64
        compiler=gcc
        compiler.version=11
        compiler.libcxx=libstdc++11
        build_type=Release
    """)

    client = TestClient(path_with_spaces=False)
    client.save({client.cache.settings_path: settings_yml})
    client.save({"host_profile": host_profile})
    client.save({"build_profile": build_profile})

    client.run("new autotools_lib -d name=hello -d version=0.1")
    client.run("create . --profile:build=build_profile --profile:host=host_profile -tf=\"\"")

    assert "--host=hexagon-acme-linux-gnu" in client.out
    assert "checking host system type... hexagon-acme-linux-gnu" in client.out
