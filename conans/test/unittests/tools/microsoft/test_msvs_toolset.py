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
def test_visual_studio_default(compiler_version, expected_toolset):
    """ When running Visual Studio as compiler, and there is no toolset configured,
        msvs_toolset must return a specific version based on the compiler version
    """
    conanfile = ConanFileMock()
    conanfile.settings = MockSettings({"compiler": "Visual Studio", "compiler.version": compiler_version})
    assert expected_toolset == msvs_toolset(conanfile)


@pytest.mark.parametrize("compiler_version,default_toolset,expected_toolset", [
    ("16", "v142", "v142_xp"),
    ("15", "v141", "v141_xp"),
    ("14", "v140", "v140_xp"),
    ("12", "v120", "v120_xp"),
    ("11", "v110", "v110_xp")])
def test_visual_studio_custom(compiler_version, default_toolset, expected_toolset):
    """ When running Visual Studio as compiler, and there is a toolset configured,
        msvs_toolset must return the specified toolset from profile
    """
    conanfile = ConanFileMock()
    conanfile.settings = MockSettings({"compiler": "Visual Studio",
                             "compiler.version": compiler_version,
                             "compiler.toolset": expected_toolset})
    assert expected_toolset == msvs_toolset(conanfile)


def test_invalid_compiler():
    """ When the compiler version is unknown and there is no toolset configured,
        msvs_toolset must return None
    """
    conanfile = ConanFileMock()
    conanfile.settings = MockSettings({"compiler": "Visual Studio",
                                       "compiler.version": "20220203"})
    assert msvs_toolset(conanfile) is None


@pytest.mark.parametrize("compiler_version,expected_toolset", [
    ("193", "v143"),
    ("192", "v142"),
    ("191", "v141"),
    ("190", "v140"),
    ("180", "v120"),
    ("170", "v110")])
def test_msvc_default(compiler_version, expected_toolset):
    """ When running msvc as compiler, and there is no toolset configured,
        msvs_toolset must return a specific version based on the compiler version
    """
    conanfile = ConanFileMock()
    conanfile.settings = MockSettings({"compiler": "msvc", "compiler.version": compiler_version})
    assert expected_toolset == msvs_toolset(conanfile)


@pytest.mark.parametrize("compiler_version,default_toolset,expected_toolset", [
    ("193", "v143", "v143_xp"),
    ("192", "v142", "v142_xp"),
    ("191", "v141", "v141_xp"),
    ("190", "v140", "v140_xp"),
    ("180", "v120", "v120_xp"),
    ("170", "v110", "v110_xp")])
def test_msvc_custom(compiler_version, default_toolset, expected_toolset):
    """ When running msvc as compiler, and there is a toolset configured,
        msvs_toolset must return the specified toolset from profile
    """
    conanfile = ConanFileMock()
    conanfile.settings = MockSettings({"compiler": "msvc",
                             "compiler.version": compiler_version,
                             "compiler.toolset": expected_toolset})
    assert expected_toolset == msvs_toolset(conanfile)
