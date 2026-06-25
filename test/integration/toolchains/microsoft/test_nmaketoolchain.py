import platform
import textwrap

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() != "Windows", reason="NMake toolchain is Windows-only")
def test_nmaketoolchain_rcflags():
    """Test that tools.build:rcflags is applied to RCFLAGS in the NMake toolchain environment."""
    profile = textwrap.dedent("""\
        include(default)
        [settings]
        arch=x86_64
        [conf]
        tools.build:rcflags=["/nologo", "/flag-rc1"]
        """)
    client = TestClient()
    conanfile = GenConanfile().with_settings("os", "arch", "compiler", "build_type").with_generator("NMakeToolchain")
    client.save({"conanfile.py": conanfile, "profile": profile})
    client.run("install . -pr profile")
    script = client.load("conannmaketoolchain.bat")
    assert "RCFLAGS" in script
    assert "/nologo" in script or "nologo" in script
    assert "/flag-rc1" in script or "flag-rc1" in script
