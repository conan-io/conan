import pytest

from conan.tools.microsoft import check_min_vs
from conans.errors import ConanInvalidConfiguration
from conans.test.utils.mocks import MockConanfile, MockSettings


class TestCheckMinVS:

    @staticmethod
    def _create_conanfile(compiler, version, update=None):
        settings = MockSettings({"compiler": compiler,
                                 "compiler.version": version,
                                 "compiler.update": update})
        conanfile = MockConanfile(settings)
        return conanfile

    @pytest.mark.parametrize("compiler,version,update,minimum", [
        ("Visual Studio", "15", None, "191"),
        ("Visual Studio", "16", None, "192"),
        ("msvc", "193", None, "193"),
        ("msvc", "193", None, "192"),
        ("msvc", "193", "2", "193.1"),
    ])
    def test_valid(self, compiler, version, update, minimum):
        conanfile = self._create_conanfile(compiler, version, update)
        check_min_vs(conanfile, minimum)

    @pytest.mark.parametrize("compiler,version,update,minimum", [
        ("Visual Studio", "15", None, "192"),
        ("Visual Studio", "16", None, "193.1"),
        ("msvc", "192", None, "193"),
        ("msvc", "193", None, "193.1"),
        ("msvc", "193", "1", "193.2"),
    ])
    def test_invalid(self, compiler, version, update, minimum):
        conanfile = self._create_conanfile(compiler, version, update)
        with pytest.raises(ConanInvalidConfiguration):
            check_min_vs(conanfile, minimum)
