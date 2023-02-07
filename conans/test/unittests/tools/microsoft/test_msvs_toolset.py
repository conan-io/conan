import pytest
from conan.tools.microsoft import msvs_toolset
from conan.errors import ConanException
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
    assert msvs_toolset(conanfile) == expected_toolset


@pytest.mark.parametrize("compiler_version,toolset,expected_toolset", [
    ("16", "v142_xp", "v142_xp"),
    ("15", "v141_xp", "v141_xp"),
    ("14", "v140_xp", "v140_xp"),
    ("12", "v120_xp", "v120_xp"),
    ("11", "v110_xp", "v110_xp")])
def test_visual_studio_custom(compiler_version, toolset, expected_toolset):
    """ When running Visual Studio as compiler, and there is a toolset configured,
        msvs_toolset must return the specified toolset from profile
    """
    conanfile = ConanFileMock()
    conanfile.settings = MockSettings({"compiler": "Visual Studio",
                             "compiler.version": compiler_version,
                             "compiler.toolset": toolset})
    assert msvs_toolset(conanfile) == expected_toolset


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
    assert msvs_toolset(conanfile) == expected_toolset


@pytest.mark.parametrize("compiler_version,toolset,expected_toolset", [
    ("193", "v143_xp", "v143_xp"),
    ("192", "v142_xp", "v142_xp"),
    ("191", "v141_xp", "v141_xp"),
    ("190", "v140_xp", "v140_xp"),
    ("180", "v120_xp", "v120_xp"),
    ("170", "v110_xp", "v110_xp")])
def test_msvc_custom(compiler_version, toolset, expected_toolset):
    """ When running msvc as compiler, and there is a toolset configured,
        msvs_toolset must return the specified toolset from profile
    """
    conanfile = ConanFileMock()
    conanfile.settings = MockSettings({"compiler": "msvc",
                             "compiler.version": compiler_version,
                             "compiler.toolset": toolset})
    assert msvs_toolset(conanfile) == expected_toolset


@pytest.mark.parametrize("compiler_version,expected_toolset", [
    ("19.1", "Intel C++ Compiler 19.1"),
    ("19", "Intel C++ Compiler 19.0"),
    ("18", "Intel C++ Compiler 18.0"),
    ("17", "Intel C++ Compiler 17.0")])
def test_intel_default(compiler_version, expected_toolset):
    """ When running intel as compiler, and there is a compiler version configured,
        msvs_toolset must return the compiler version as its toolset
    """
    conanfile = ConanFileMock()
    conanfile.settings = MockSettings({"compiler": "intel", "compiler.version": compiler_version})
    assert msvs_toolset(conanfile) == expected_toolset


def test_intel_invalid():
    """ When running intel as compiler, and there is no compiler version configured,
        msvs_toolset must return None
    """
    conanfile = ConanFileMock()
    conanfile.settings = MockSettings({"compiler": "intel"})
    assert msvs_toolset(conanfile) is None


def test_intel_cc_old_compiler():
    """ When running intel-cc as compiler, and the compiler version configured is older than 2021
        msvs_toolset must raise an ConanExpection
    """
    conanfile = ConanFileMock()
    conanfile.settings = MockSettings({"compiler": "intel-cc", "compiler.version": "19.1"})
    with pytest.raises(ConanException) as error:
        msvs_toolset(conanfile)
    assert "You have to use 'intel' compiler" in str(error.value)


@pytest.mark.parametrize("compiler_version,compiler_mode,expected_toolset", [
    ("2021.3", "classic", "Intel C++ Compiler 19.2"),
    ("2021.2", "classic", "Intel C++ Compiler 19.2"),
    ("2021.1", "classic", "Intel C++ Compiler 19.2"),
    ("2021.3", "icx", "Intel C++ Compiler 2021"),
    ("2021.2", "icx", "Intel C++ Compiler 2021"),
    ("2021.1", "icx", "Intel C++ Compiler 2021"),
    ("2021.3", "dpcpp", "Intel(R) oneAPI DPC++ Compiler"),
    ("2021.2", "dpcpp", "Intel(R) oneAPI DPC++ Compiler"),
    ("2021.1", "dpcpp", "Intel(R) oneAPI DPC++ Compiler"),
    ("2021.3", None, "Intel(R) oneAPI DPC++ Compiler")])
def test_intel_cc_default(compiler_version, compiler_mode, expected_toolset):
    """ When running intel-cc as compiler, and there is a proper compiler version configured,
        and the compiler.mode is configured,
        msvs_toolset must return a compiler toolset based on compiler.mode
    """
    conanfile = ConanFileMock()
    conanfile.settings = MockSettings({"compiler": "intel-cc",
                                       "compiler.version": compiler_version,
                                       "compiler.mode": compiler_mode})
    assert msvs_toolset(conanfile) == expected_toolset
