import platform
import textwrap

import pytest

from conan.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows")
def test_msbuildtoolchain_props_with_extra_flags():
    """
    Real test which is injecting some compiler/linker options and other dummy defines and
    checking that they are being processed somehow.

    Expected result: everything was built successfully.
    """
    profile = textwrap.dedent("""\
    include(default)

    [conf]
    tools.build:cxxflags=["/analyze:quiet"]
    tools.build:cflags+=["/doc"]
    tools.build:sharedlinkflags+=["/VERBOSE:UNUSEDLIBS"]
    tools.build:exelinkflags+=["/PDB:mypdbfile"]
    tools.build:defines+=["DEF1", "DEF2"]
    """)
    client = TestClient(path_with_spaces=False)
    client.run("new msbuild_exe -d name=hello -d version=0.1")
    client.save({"myprofile": profile})
    #  conantoolchain.props is already imported in the msbuild_exe tempalte
    client.run("create . -pr myprofile -tf=")
    assert "/analyze:quiet /doc src/hello.cpp" in client.out
    assert r"/VERBOSE:UNUSEDLIBS /PDB:mypdbfile x64\Release\hello.obj" in client.out
    assert "/D DEF1 /D DEF2" in client.out
    assert "Build succeeded." in client.out


@pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows")
def test_msbuildtoolchain_winsdk_version():
    """
    Configure sdk_version
    """
    client = TestClient(path_with_spaces=False)
    client.run("new msbuild_lib -d name=hello -d version=0.1")
    #  conantoolchain.props is already imported in the msbuild_exe tempalte
    client.run("create . -s arch=x86_64 -s compiler.version=193 "
               "-c tools.microsoft:winsdk_version=8.1")
    # I have verified also opening VS IDE that the setting is correctly configured
    # because the test always run over vcvars that already activates it
    assert "amd64 - winsdk_version=8.1 - vcvars_ver=14.3" in client.out
