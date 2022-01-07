import os
import platform
import sys
import textwrap

import pytest

from conans.test.assets.sources import gen_function_cpp
from conans.test.utils.tools import TestClient


@pytest.mark.tool_meson
@pytest.mark.skipif(sys.version_info.major == 2, reason="Meson not supported in Py2")
@pytest.mark.skipif(platform.system() != "Windows", reason="requires Windows")
def test_cross_x86():
    conanfile_py = textwrap.dedent("""
        from conans import ConanFile, tools
        from conan.tools.meson import Meson, MesonToolchain


        class App(ConanFile):
            settings = "os", "arch", "compiler", "build_type"
            options = {"shared": [True, False], "fPIC": [True, False]}
            default_options = {"shared": False, "fPIC": True}

            def config_options(self):
                if self.settings.os == "Windows":
                    del self.options.fPIC

            def layout(self):
                self.folders.build = "build"

            def generate(self):
                tc = MesonToolchain(self, backend='vs')
                tc.generate()

            def build(self):
                meson = Meson(self)
                meson.configure()
                meson.build()
        """)
    meson_build = textwrap.dedent("""
        project('tutorial', 'cpp')
        executable('demo', 'main.cpp')
        """)
    main_cpp = gen_function_cpp(name="main")
    client = TestClient()
    client.save({"conanfile.py": conanfile_py,
                 "meson.build": meson_build,
                 "main.cpp": main_cpp})
    client.run("install .")
    content = client.load("conan_meson_native.ini")
    assert "backend = 'vs'" in content
    client.run("build .")
    assert "Auto detected Visual Studio backend" in client.out
    client.run_command(os.path.join("build", "demo"))

    assert "main _M_X64 defined" in client.out
    assert "main _MSC_VER19" in client.out
    assert "main _MSVC_LANG2014" in client.out
