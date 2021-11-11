import os
import platform
import sys
import textwrap

import pytest

from conans.test.assets.sources import gen_function_cpp
from conans.test.utils.tools import TestClient


@pytest.mark.tool_meson
@pytest.mark.skipif(sys.version_info.major == 2, reason="Meson not supported in Py2")
# for Linux, build for x86 will require a multilib compiler
# for macOS, build for x86 is no longer supported by modern Xcode
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

            def generate(self):
                tc = MesonToolchain(self)
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
    profile_x86 = textwrap.dedent("""
        include(default)
        [settings]
        arch=x86
        [buildenv]
        CC=cl
        CXX=cl
        """)

    client = TestClient()
    client.save({"conanfile.py": conanfile_py,
                 "meson.build": meson_build,
                 "main.cpp": main_cpp,
                 "x86": profile_x86})
    profile_str = "--profile:build=default --profile:host=x86"
    client.run("build . %s" % profile_str)
    client.run_command(os.path.join("build", "demo"))

    assert "main _M_IX86 defined" in client.out
    assert "main _MSC_VER19" in client.out
    assert "main _MSVC_LANG2014" in client.out
