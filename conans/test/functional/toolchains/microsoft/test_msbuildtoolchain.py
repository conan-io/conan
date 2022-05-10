import platform
import sys
import textwrap
import os

import pytest
try:
    from unittest.mock import MagicMock
except:
    from mock import MagicMock

from conan.tools.files import replace_in_file
from conans.test.utils.tools import TestClient

toolchain_props = """
  <ImportGroup Label="PropertySheets">
      <Import Project="conan\\conantoolchain_release_x64.props" />
"""


@pytest.mark.skipif(sys.version_info.major == 2, reason="Meson not supported in Py2")
@pytest.mark.skipif(platform.system() not in ["Windows"], reason="Requires Windows")
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
    client.run("new hello/0.1 --template=msbuild_exe")
    client.save({
        "myprofile": profile
    })
    # Let's import manually the created conantoolchain_release_x64.props
    replace_in_file(MagicMock(), os.path.join(client.current_folder, "hello.vcxproj"),
                    r'  <ImportGroup Label="PropertySheets">', toolchain_props)
    client.run("create . -pr myprofile -tf None")
    assert "/analyze:quiet /doc src/hello.cpp" in client.out
    assert r"/VERBOSE:UNUSEDLIBS /PDB:mypdbfile x64\Release\hello.obj" in client.out
    assert "/D DEF1 /D DEF2" in client.out
    assert "Build succeeded." in client.out
