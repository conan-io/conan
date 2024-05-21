import pytest

from conan.tools.microsoft import check_min_vs
from conans.errors import ConanInvalidConfiguration
from conan.test.utils.mocks import ConanFileMock, MockSettings


class TestCheckMinVS:

    parametrize_vars = "compiler,version,update,minimum"
    valid_parametrize_values = [
        ("Visual Studio", "15", None, "191"),
        ("Visual Studio", "16", None, "192"),
        ("msvc", "193", None, "193"),
        ("msvc", "193", None, "192"),
        ("msvc", "193", "2", "193.1"),
    ]

    invalid_parametrize_values = [
        ("Visual Studio", "15", None, "192"),
        ("Visual Studio", "16", None, "193.1"),
        ("msvc", "192", None, "193"),
        ("msvc", "193", None, "193.1"),
        ("msvc", "193", "1", "193.2"),
    ]

    @staticmethod
    def _create_conanfile(compiler, version, update=None):
        settings = MockSettings({"compiler": compiler,
                                 "compiler.version": version,
                                 "compiler.update": update})
        conanfile = ConanFileMock(settings)
        return conanfile

    @pytest.mark.parametrize(parametrize_vars, valid_parametrize_values)
    def test_valid(self, compiler, version, update, minimum):
        conanfile = self._create_conanfile(compiler, version, update)
        check_min_vs(conanfile, minimum)

    @pytest.mark.parametrize(parametrize_vars, valid_parametrize_values)
    def test_valid_nothrows(self, compiler, version, update, minimum):
        conanfile = self._create_conanfile(compiler, version, update)
        assert check_min_vs(conanfile, minimum, raise_invalid=False)

    @pytest.mark.parametrize(parametrize_vars, invalid_parametrize_values)
    def test_invalid(self, compiler, version, update, minimum):
        conanfile = self._create_conanfile(compiler, version, update)
        with pytest.raises(ConanInvalidConfiguration):
            check_min_vs(conanfile, minimum)

    @pytest.mark.parametrize(parametrize_vars, invalid_parametrize_values)
    def test_invalid_nothrows(self, compiler, version, update, minimum):
        conanfile = self._create_conanfile(compiler, version, update)
        assert not check_min_vs(conanfile, minimum, raise_invalid=False)
