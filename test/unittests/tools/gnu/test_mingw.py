import pytest

from conan import ConanFile
from conan.tools.gnu import is_mingw
from conan.internal.model.settings import Settings


def _make_conanfile(os_, compiler, version, *, libcxx=None, runtime=None,
                    runtime_type=None, subsystem=None):
    compiler_def = {compiler: {"version": [version]}}
    if libcxx is not None:
        compiler_def[compiler]["libcxx"] = [libcxx]
    if runtime is not None:
        compiler_def[compiler]["runtime"] = [runtime]
    if runtime_type is not None:
        compiler_def[compiler]["runtime_type"] = [runtime_type]
    os_def = {os_: {"subsystem": [subsystem]}} if subsystem else [os_]
    settings = Settings({
        "os": os_def,
        "arch": ["x86_64"],
        "compiler": compiler_def,
        "build_type": ["Release"],
    })
    conanfile = ConanFile()
    conanfile.settings = settings
    conanfile.settings.os = os_
    if subsystem is not None:
        conanfile.settings.os.subsystem = subsystem
    conanfile.settings.compiler = compiler
    conanfile.settings.compiler.version = version
    if libcxx is not None:
        conanfile.settings.compiler.libcxx = libcxx
    if runtime is not None:
        conanfile.settings.compiler.runtime = runtime
    if runtime_type is not None:
        conanfile.settings.compiler.runtime_type = runtime_type
    return conanfile


@pytest.mark.parametrize("os_,compiler,version,kwargs,expected", [
    # MinGW with gcc — the canonical case
    ("Windows", "gcc", "13", {"libcxx": "libstdc++11"}, True),
    # MinGW with Clang — `compiler.runtime` is unset
    ("Windows", "clang", "17", {"libcxx": "libstdc++11"}, True),
    # clang-cl on Windows — `compiler.runtime` is set, not MinGW
    ("Windows", "clang", "17", {"runtime": "dynamic", "runtime_type": "Release"}, False),
    # MSVC — never MinGW
    ("Windows", "msvc", "193", {"runtime": "dynamic", "runtime_type": "Release"}, False),
    # Cygwin uses a POSIX layer, not MinGW
    ("Windows", "gcc", "13", {"subsystem": "cygwin", "libcxx": "libstdc++11"}, False),
    # Non-Windows hosts are never MinGW
    ("Linux", "gcc", "13", {"libcxx": "libstdc++11"}, False),
    ("Linux", "clang", "17", {"libcxx": "libc++"}, False),
    ("Macos", "apple-clang", "15", {"libcxx": "libc++"}, False),
])
def test_is_mingw(os_, compiler, version, kwargs, expected):
    conanfile = _make_conanfile(os_, compiler, version, **kwargs)
    assert is_mingw(conanfile) is expected


def test_is_mingw_build_context():
    """`build_context=True` must consult settings_build, not the host settings."""
    host = _make_conanfile("Linux", "gcc", "13", libcxx="libstdc++11")
    build = _make_conanfile("Windows", "gcc", "13", libcxx="libstdc++11")
    host.settings_build = build.settings
    assert is_mingw(host) is False
    assert is_mingw(host, build_context=True) is True


def test_is_mingw_libcxx_not_required():
    """`compiler.libcxx` is removed in pure-C recipes; detection must still work without it."""
    settings = Settings({
        "os": ["Windows"],
        "arch": ["x86_64"],
        "compiler": {"gcc": {"version": ["13"]}},
        "build_type": ["Release"],
    })
    conanfile = ConanFile()
    conanfile.settings = settings
    conanfile.settings.os = "Windows"
    conanfile.settings.compiler = "gcc"
    conanfile.settings.compiler.version = "13"
    assert is_mingw(conanfile) is True
