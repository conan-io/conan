import platform
import textwrap

import pytest
from parameterized import parameterized

from conan.test.utils.tools import TestClient


@parameterized.expand([("msvc", "190", "dynamic"),
                       ("msvc", "191", "static")]
                      )
@pytest.mark.tool("visual_studio")
@pytest.mark.skipif(platform.system() != "Windows", reason="Only for windows")
def test_toolchain_win(compiler, version, runtime):
    client = TestClient(path_with_spaces=False)
    settings = {"compiler": compiler,
                "compiler.version": version,
                "compiler.cppstd": "14",
                "compiler.runtime": runtime,
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
    if version == "190":
        assert "<PlatformToolset>v140</PlatformToolset>" in props
    else:
        assert "<PlatformToolset>v141</PlatformToolset>" in props
    if runtime == "dynamic":
        assert "<RuntimeLibrary>MultiThreadedDLL</RuntimeLibrary>" in props
    else:
        assert "<RuntimeLibrary>MultiThreaded</RuntimeLibrary>" in props
