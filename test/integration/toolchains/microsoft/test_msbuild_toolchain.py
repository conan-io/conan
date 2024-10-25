import platform
import textwrap

import pytest

from conan.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() != "Windows", reason="Only for windows")
@pytest.mark.tool("visual_studio")
@pytest.mark.tool("clang", "16")
@pytest.mark.parametrize(
    "compiler, version",
    [
        ("msvc", "190"),
        ("msvc", "191"),
        ("clang", "16")
    ],
)
@pytest.mark.parametrize("runtime", ["dynamic", "static"])
@pytest.mark.parametrize("runtime_type", ["Release", "Debug"])
def test_toolchain_win(compiler, version, runtime, runtime_type):
    client = TestClient(path_with_spaces=False)
    settings = {"compiler": compiler,
                "compiler.version": version,
                "compiler.cppstd": "14",
                "compiler.runtime": runtime,
                "compiler.runtime_type": runtime_type,
                "build_type": "Release",
                "arch": "x86_64"}

    # Build the profile according to the settings provided
    settings = " ".join('-s %s="%s"' % (k, v) for k, v in settings.items() if v)

    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.microsoft import MSBuildToolchain
        class Pkg(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            def generate(self):
                msbuild = MSBuildToolchain(self)
                msbuild.properties["IncludeExternals"] = "true"
                msbuild.generate()
            """)
    client.save({"conanfile.py": conanfile})
    client.run("install . {}".format(settings))
    props = client.load("conantoolchain_release_x64.props")
    assert "<IncludeExternals>true</IncludeExternals>" in props
    assert "<LanguageStandard>stdcpp14</LanguageStandard>" in props
    if compiler == "msvc":
        if version == "190":
            assert "<PlatformToolset>v140</PlatformToolset>" in props
        elif version == "191":
            assert "<PlatformToolset>v141</PlatformToolset>" in props
    elif compiler == "clang":
        assert "<PlatformToolset>ClangCl</PlatformToolset>" in props
    if runtime == "dynamic":
        if runtime_type == "Release":
            assert "<RuntimeLibrary>MultiThreadedDLL</RuntimeLibrary>" in props
        else:
            assert "<RuntimeLibrary>MultiThreadedDebugDLL</RuntimeLibrary>" in props
    else:
        if runtime_type == "Release":
            assert "<RuntimeLibrary>MultiThreaded</RuntimeLibrary>" in props
        else:
            assert "<RuntimeLibrary>MultiThreadedDebug</RuntimeLibrary>" in props
