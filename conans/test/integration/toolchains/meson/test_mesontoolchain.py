import textwrap

from conan.tools.meson import MesonToolchain
from conans.test.utils.tools import TestClient


def test_apple_meson_keep_user_flags():
    profile = textwrap.dedent("""
    [settings]
    os=Macos
    os_build=Macos
    arch=x86_64
    compiler=apple-clang
    compiler.version=12.0
    compiler.libcxx=libc++
    build_type=Release

    [buildenv]
    {build_env}
    """)

    _conanfile_py = textwrap.dedent("""
    from conan import ConanFile
    from conan.tools.meson import MesonToolchain

    class App(ConanFile):
        settings = "os", "arch", "compiler", "build_type"

        def generate(self):
            tc = MesonToolchain(self)
            tc.generate()
    """)

    t = TestClient()
    t.save({"conanfile.py": _conanfile_py,
            "profile": profile.format(build_env="CFLAGS=-arch armv7")})
    t.run("install . -pr profile")
    expected_args = textwrap.dedent("""
    c_args = ['-arch', 'armv7'] + preprocessor_definitions
    c_link_args = ['-arch', 'x86_64']
    cpp_args = ['-arch', 'x86_64'] + preprocessor_definitions
    cpp_link_args = ['-arch', 'x86_64']
    """)
    content = t.load(MesonToolchain.native_filename)
    assert expected_args in content
