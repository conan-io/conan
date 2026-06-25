import os
import platform
import textwrap

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() == "Windows", reason="QbsProfile requires host compiler (gcc) to be found")
def test_qbsprofile_rcflags():
    """Test that tools.build:rcflags is applied to cpp.rcFlags in qbs_settings.txt."""
    profile = textwrap.dedent("""
        [settings]
        os=Linux
        arch=x86_64
        compiler=gcc
        compiler.version=9
        compiler.libcxx=libstdc++
        build_type=Release

        [conf]
        tools.build:rcflags=["-rcflag1", "-rcflag2"]
        """)
    client = TestClient()
    conanfile = GenConanfile().with_settings("os", "arch", "compiler", "build_type").with_generator("QbsProfile")
    client.save({"conanfile.py": conanfile, "profile": profile})
    client.run("install . --profile:build=profile --profile:host=profile")
    settings_path = os.path.join(client.current_folder, "qbs_settings.txt")
    assert os.path.exists(settings_path)
    content = client.load("qbs_settings.txt")
    assert "cpp.rcFlags" in content
    assert "-rcflag1" in content
    assert "-rcflag2" in content
