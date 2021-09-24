import pytest


@pytest.mark.xfail(reason="update tests for NewCppInfo")
def test_set_get_properties():
    cpp_info = _CppInfo()

    assert not cpp_info.get_property("my_property")
    assert not cpp_info.get_property("my_property", "some_generator")

    cpp_info.set_property("my_property", "default_value")
    assert cpp_info.get_property("my_property") == "default_value"
    # can you do a get_property for just a family without generator?
    assert cpp_info.get_property("my_property", generator="cmake_multi") == "default_value"
    assert cpp_info.get_property("my_property", generator="pkg_config") == "default_value"

    cpp_info.set_property("my_property", "pkg_config_value", generator="pkg_config")
    assert cpp_info.get_property("my_property", generator="pkg_config") == "pkg_config_value"
    cpp_info.set_property("other_property", "other_pkg_config_value", generator="pkg_config")
    assert not cpp_info.get_property("other_property")
    assert cpp_info.get_property("other_property", generator="pkg_config") == "other_pkg_config_value"
