import os

import pytest

from conans.test.utils.tools import TestClient


@pytest.mark.parametrize(
    "arch,exp_platform",
    [
        ("x86", "Win32"),
        ("x86_64", "x64"),
        ("armv7", "ARM"),
        ("armv8", "ARM64"),
    ],
)
def test_msbuilddeps_maps_architecture_to_platform(arch, exp_platform):
    client = TestClient(path_with_spaces=False)
    client.run("new hello/0.1 --template=msbuild_lib")
    client.run(f"install . -g MSBuildDeps -s arch={arch} -pr:b=default -if=install")
    toolchain = client.load(os.path.join("conan", "conantoolchain.props"))
    expected_import = f"""<Import Condition="'$(Configuration)' == 'Release' And '$(Platform)' == '{exp_platform}'" Project="conantoolchain_release_{exp_platform.lower()}.props"/>"""
    assert expected_import in toolchain
