import os
import textwrap

from conans.test.assets.sources import gen_function_cpp, gen_function_h
from conans.test.functional.toolchains.meson._base import TestMesonBase


class MesonConfTest(TestMesonBase):
    _conanfile_py = textwrap.dedent("""
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

    _meson_build = textwrap.dedent("""
    project('tutorial', 'cpp')
    hello = library('hello', 'hello.cpp')
    executable('demo', 'main.cpp', link_with: hello)
    """)

    def test_build(self):
        hello_h = gen_function_h(name="hello")
        hello_cpp = gen_function_cpp(name="hello")
        app = gen_function_cpp(name="main", includes=["hello"], calls=["hello"])

        profile_host = textwrap.dedent("""
    include(default)
    [settings]
    arch=armv8
    os=FreeBSD
    [conf]
    tools.meson.mesontoolchain.host_machine:system=nes
    tools.meson.mesontoolchain.host_machine:cpu_family=MOS
    tools.meson.mesontoolchain.host_machine:cpu=6502
    tools.meson.mesontoolchain.host_machine:endian=big
    
    tools.meson.mesontoolchain.build_machine:system=smd
    tools.meson.mesontoolchain.build_machine:cpu_family=Motorola
    tools.meson.mesontoolchain.build_machine:cpu=68K
    tools.meson.mesontoolchain.build_machine:endian=big
    
    tools.meson.mesontoolchain.target_machine:system=spectrum
    tools.meson.mesontoolchain.target_machine:cpu_family=Zilog
    tools.meson.mesontoolchain.target_machine:cpu=Z80
    tools.meson.mesontoolchain.target_machine:endian=big
    """)

        self.t.save({"conanfile.py": self._conanfile_py,
                     "meson.build": self._meson_build,
                     "hello.h": hello_h,
                     "hello.cpp": hello_cpp,
                     "main.cpp": app,
                     "profile_host": profile_host})

        self.t.run("install . %s -pr:b=default -pr:h=profile_host" % self._settings_str)

        content = self.t.load("conan_meson_cross.ini")

        self.assertIn("[host_machine]\n\n"
                      "system = 'nes'\n"
                      "cpu_family = 'MOS'\n"
                      "cpu = '6502'\n"
                      "endian = 'big", content)

        self.assertIn("[build_machine]\n\n"
                      "system = 'smd'\n"
                      "cpu_family = 'Motorola'\n"
                      "cpu = '68K'\n"
                      "endian = 'big", content)

        self.assertIn("[target_machine]\n\n"
                      "system = 'spectrum'\n"
                      "cpu_family = 'Zilog'\n"
                      "cpu = 'Z80'\n"
                      "endian = 'big", content)
