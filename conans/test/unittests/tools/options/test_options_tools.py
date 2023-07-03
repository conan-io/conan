from conan.tools.options import (
    handle_common_config_options,
    handle_common_configure_options, handle_common_package_id_options
)
from conans.test.utils.mocks import MockSettings, ConanFileMock, MockOptions, MockConanfile


def test_handle_common_config_options():
    """
    If windows, then fpic option should be removed
    """
    conanfile = ConanFileMock()
    conanfile.settings = MockSettings({"os": "Linux"})
    conanfile.options = MockOptions({"shared": False, "fPIC": False})
    handle_common_config_options(conanfile)
    assert conanfile.options.values == {"shared": False, "fPIC": False}
    conanfile.settings = MockSettings({"os": "Windows"})
    handle_common_config_options(conanfile)
    assert conanfile.options.values == {"shared": False}


def test_handle_common_configure_options():
    """
    If header only, fpic and shared options should be removed.
    If shared, fpic removed and header only is false
    """
    conanfile = ConanFileMock()
    conanfile.settings = MockSettings({"os": "Linux"})
    conanfile.options = MockOptions({"header_only": False, "shared": False, "fPIC": False})
    handle_common_configure_options(conanfile)
    assert conanfile.options.values == {"header_only": False, "shared": False, "fPIC": False}
    conanfile.options = MockOptions({"header_only": True, "shared": False, "fPIC": False})
    handle_common_configure_options(conanfile)
    assert conanfile.options.values == {"header_only": True}
    conanfile.options = MockOptions({"header_only": False, "shared": True, "fPIC": False})
    handle_common_configure_options(conanfile)
    assert conanfile.options.values == {"header_only": False, "shared": True}
    # Wrong options combination, but result should be right as well
    conanfile.options = MockOptions({"header_only": True, "shared": True, "fPIC": False})
    handle_common_configure_options(conanfile)
    assert conanfile.options.values == {"header_only": True}


def test_handle_common_package_id_options():
    """
    When header_only option is False, the original settings and options is kept in package id info
    When the heacer_only option is True, the package id info is cleared
    """
    original_settings = {"os": "Linux", "compiler": "gcc"}
    options = MockOptions({"header_only": False})
    conanfile = MockConanfile(original_settings, options)
    handle_common_package_id_options(conanfile)
    assert conanfile.info.settings == original_settings
    assert conanfile.info.options == options

    options = MockOptions({"header_only": True})
    conanfile = MockConanfile(original_settings, options)
    handle_common_package_id_options(conanfile)
    assert conanfile.info.settings == {}
    assert conanfile.info.options == {}
