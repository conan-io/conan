import pytest
from mock import Mock

from conan.tools.gnu import is_mingw
from conans import ConanFile, Settings
from conans.model.env_info import EnvValues


@pytest.mark.parametrize(
    "os,compiler_name,compiler_version,compiler_libcxx,compiler_runtime,compiler_runtime_type,expected",
    [
        ("Windows", "gcc", "9", "libstdc++11", None, None, True),
        ("Windows", "clang", "16", "libstdc++11", None, None, True),
        ("Windows", "Visual Studio", "17", "MD", None, None, False),
        ("Windows", "msvc", "193", None, "dynamic", "Release", False),
        ("Windows", "clang", "16", None, "MD", None, False),
        ("Windows", "clang", "16", None, "dynamic", "Release", False),
        ("Linux", "gcc", "9", "libstdc++11", None, None, False),
        ("Linux", "clang", "16", "libc++", None, None, False),
        ("Macos", "apple-clang", "14", "libc++", None, None, False),
    ],
)
def test_is_mingw(os, compiler_name, compiler_version, compiler_libcxx, compiler_runtime, compiler_runtime_type, expected):
    compiler = {compiler_name: {"version": [compiler_version]}}
    if compiler_libcxx:
        compiler[compiler_name].update({"libcxx": [compiler_libcxx]})
    if compiler_runtime:
        compiler[compiler_name].update({"runtime": [compiler_runtime]})
    if compiler_runtime_type:
        compiler[compiler_name].update({"runtime_type": [compiler_runtime_type]})
    settings = Settings({
        "os": [os],
        "arch": ["x86_64"],
        "compiler": compiler,
        "build_type": ["Release"],
    })
    conanfile = ConanFile(Mock(), None)
    conanfile.settings = "os", "arch", "compiler", "build_type"
    conanfile.initialize(settings, EnvValues())
    conanfile.settings.os = os
    conanfile.settings.compiler = compiler_name
    conanfile.settings.compiler.version = compiler_version
    if compiler_libcxx:
        conanfile.settings.compiler.libcxx = compiler_libcxx
    if compiler_runtime:
        conanfile.settings.compiler.runtime = compiler_runtime
    if compiler_runtime_type:
        conanfile.settings.compiler.runtime_type = compiler_runtime_type
    assert is_mingw(conanfile) == expected
