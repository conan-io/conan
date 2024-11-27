import os
import platform
import textwrap

import pytest

from conan.test.utils.tools import TestClient
from test.conftest import tools_locations


@pytest.mark.parametrize("arch, expected_arch", [('armv8', 'aarch64'),
                                                 ('armv7', 'arm'),
                                                 ('x86', 'i386'),
                                                 ('x86_64', 'x86_64')
                                                 ])
@pytest.mark.tool("android_ndk")
@pytest.mark.tool("autotools")
@pytest.mark.skipif(platform.system() != "Darwin", reason="NDK only installed on MAC")
def test_android_autotools_toolchain_cross_compiling(arch, expected_arch):
    profile_host = textwrap.dedent("""
    include(default)

    [settings]
    os = Android
    os.api_level = 21
    arch = {arch}

    [conf]
    tools.android:ndk_path={ndk_path}
    """)
    ndk_path = tools_locations["android_ndk"]["system"]["path"][platform.system()]
    profile_host = profile_host.format(
        arch=arch,
        ndk_path=ndk_path
    )

    client = TestClient(path_with_spaces=False)
    client.run("new autotools_lib -d name=hello -d version=1.0")
    client.save({"profile_host": profile_host})
    client.run("build . --profile:build=default --profile:host=profile_host")
    libhello = os.path.join("build-release", "src", ".libs", "libhello.a")
    # Check binaries architecture
    client.run_command('objdump -f "%s"' % libhello)
    assert "architecture: %s" % expected_arch in client.out
