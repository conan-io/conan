from conans.model.build_info import _CppInfo


def test_set_get_properties():
    cpp_info = _CppInfo()

    assert not cpp_info.get_property("my_property")

    cpp_info.set_property("my_property", "default_value")
    assert cpp_info.get_property("my_property") == "default_value"
    # can you do a get_property for just a family without generator?
    assert cpp_info.get_property("my_property") == "default_value"

    cpp_info.set_property("my_property", "pkg_config_value")
    assert cpp_info.get_property("my_property") == "pkg_config_value"
    cpp_info.set_property("other_property", "other_pkg_config_value")
    assert cpp_info.get_property("other_property") == "other_pkg_config_value"
