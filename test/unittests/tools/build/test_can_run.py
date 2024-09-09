import pytest

from conan.test.utils.mocks import MockSettings, ConanFileMock
from conan.tools.build import can_run


class ConfigMock:
    def __init__(self, run=None):
        self.can_run = run

    def get(self, conf_name, default=None, check_type=None):
        return self.can_run


@pytest.mark.parametrize("expected", [False, True])
def test_can_run_explicit_config(expected):
    """ When the config tools.build.cross_building:can_run is declared and evaluated (True|False),
        can_run must return the same value.
    """
    config = ConfigMock(expected)
    settings = MockSettings({"os": "Macos",
                             "compiler": "apple-clang",
                             "compiler.version": "11.0",
                             "arch": "armv8"})
    conanfile = ConanFileMock(settings)
    conanfile.conf = config
    assert expected == can_run(conanfile)


@pytest.mark.parametrize("arch, expected", [("x86_64", False), ("armv8", True)])
def test_can_run_cross_building(arch, expected):
    """ When the config is None, and is cross-building, can_run must return False.
    """
    config = ConfigMock(None)
    settings_build = MockSettings({"os": "Macos",
                             "compiler": "apple-clang",
                             "compiler.version": "11.0",
                             "arch": "armv8"})
    settings = MockSettings({"os": "Macos",
                             "compiler": "apple-clang",
                             "compiler.version": "11.0",
                             "arch": arch})
    conanfile = ConanFileMock()
    conanfile.settings = settings
    conanfile.settings_build = settings_build
    conanfile.conf = config
    assert expected == can_run(conanfile)


def test_can_run_cross_building_with_explicit():
    """ When the config is True or False, and is cross-building, can_run must follow the config.
    """
    config = ConfigMock(True)
    settings_build = MockSettings({"os": "Macos",
                             "compiler": "apple-clang",
                             "compiler.version": "11.0",
                             "arch": "armv8"})
    settings = MockSettings({"os": "Macos",
                             "compiler": "apple-clang",
                             "compiler.version": "11.0",
                             "arch": "x86_64"})
    conanfile = ConanFileMock()
    conanfile.settings = settings
    conanfile.settings_build = settings_build
    conanfile.conf = config
    assert True == can_run(conanfile)
