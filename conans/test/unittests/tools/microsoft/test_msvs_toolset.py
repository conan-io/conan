import pytest
from conan.tools.microsoft import msvs_toolset
from conans.test.utils.mocks import ConanFileMock, MockSettings

@pytest.mark.parametrize("compiler_version,expected_toolset", [
    ("17", "v143"),
    ("16", "v142"),
    ("15", "v141"),
    ("14", "v140"),
    ("12", "v120"),
    ("11", "v110"),
    ("10", "v100"),
    ("9", "v90"),
    ("8", "v80")])
def test_default(compiler_version, expected_toolset):
    conanfile = ConanFileMock()
    conanfile.settings = MockSettings({"compiler": "Visual Studio", "compiler.version": compiler_version})
    assert expected_toolset == msvs_toolset(conanfile)


@pytest.mark.parametrize("compiler_version,expected_toolset", [
    ("16", "v141_xp"),
    ("15", "v141_xp"),
    ("14", "v140_xp"),
    ("12", "v120_xp"),
    ("11", "v110_xp")])
def test_custom(compiler_version, expected_toolset):
    conanfile = ConanFileMock()
    conanfile.settings = MockSettings({"compiler": "Visual Studio",
                             "compiler.version": compiler_version,
                             "compiler.toolset": expected_toolset})
    assert expected_toolset == msvs_toolset(conanfile)


def test_negative():
    conanfile = ConanFileMock()
    conanfile.settings = MockSettings({"compiler": "Visual Studio",
                                       "compiler.version": "20220203"})
    assert msvs_toolset(conanfile) == ""
