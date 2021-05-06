import pytest

from conans.model.build_info import CppInfo
from conans.model.new_build_info import NewCppInfo, _DIRS_VAR_NAMES, _FIELD_VAR_NAMES, \
    fill_old_cppinfo, from_old_cppinfo


def test_components_order():
    cppinfo = NewCppInfo()
    cppinfo.components["c1"].requires = ["c4", "OtherPackage::OtherComponent2"]
    cppinfo.components["c2"].requires = ["OtherPackage::OtherComponent"]
    cppinfo.components["c3"].requires = ["c2"]
    cppinfo.components["c4"].requires = ["c3"]
    sorted_c = list(cppinfo.get_sorted_components().keys())
    assert sorted_c == ["c2", "c3", "c4", "c1"]


def test_generator_properties_copy():
    cppinfo = NewCppInfo()
    cppinfo.set_property("foo", "foo_value", "generator1")
    cppinfo.set_property("foo", "var_value", "generator2")
    cppinfo.set_property("foo2", "foo2_value", "generator1")

    copied = cppinfo.copy()

    assert copied.get_property("foo") is None
    assert copied.get_property("foo", "generator1") == "foo_value"
    assert copied.get_property("foo", "generator2") == "var_value"


def test_component_aggregation():
    cppinfo = NewCppInfo()

    cppinfo.includedirs = ["includedir"]
    cppinfo.libdirs = ["libdir"]
    cppinfo.srcdirs = ["srcdir"]
    cppinfo.bindirs = ["bindir"]
    cppinfo.builddirs = ["builddir"]
    cppinfo.frameworkdirs = ["frameworkdir"]

    cppinfo.components["c2"].includedirs = ["includedir_c2"]
    cppinfo.components["c2"].libdirs = ["libdir_c2"]
    cppinfo.components["c2"].srcdirs = ["srcdir_c2"]
    cppinfo.components["c2"].bindirs = ["bindir_c2"]
    cppinfo.components["c2"].builddirs = ["builddir_c2"]
    cppinfo.components["c2"].frameworkdirs = ["frameworkdir_c2"]
    cppinfo.components["c2"].cxxflags = ["cxxflags_c2"]
    cppinfo.components["c2"].defines = ["defines_c2"]
    cppinfo.components["c2"].set_property("my_foo", ["bar", "bar2"])

    cppinfo.components["c1"].requires = ["c2", "LIB_A::C1"]
    cppinfo.components["c1"].includedirs = ["includedir_c1"]
    cppinfo.components["c1"].libdirs = ["libdir_c1"]
    cppinfo.components["c1"].srcdirs = ["srcdir_c1"]
    cppinfo.components["c1"].bindirs = ["bindir_c1"]
    cppinfo.components["c1"].builddirs = ["builddir_c1"]
    cppinfo.components["c1"].frameworkdirs = ["frameworkdir_c1"]
    cppinfo.components["c1"].cxxflags = ["cxxflags_c1"]
    cppinfo.components["c1"].defines = ["defines_c1"]
    cppinfo.components["c1"].set_property("my_foo", "jander")
    cppinfo.components["c1"].set_property("my_foo2", "bar2", "other_gen")

    ret = cppinfo.copy()
    ret.aggregate_components()

    assert ret.includedirs == ["includedir_c1", "includedir_c2"]
    assert ret.libdirs == ["libdir_c1", "libdir_c2"]
    assert ret.srcdirs == ["srcdir_c1", "srcdir_c2"]
    assert ret.bindirs == ["bindir_c1", "bindir_c2"]
    assert ret.builddirs == ["builddir_c1", "builddir_c2"]
    assert ret.frameworkdirs == ["frameworkdir_c1", "frameworkdir_c2"]
    assert ret.cxxflags == ["cxxflags_c1", "cxxflags_c2"]
    assert ret.defines == ["defines_c1", "defines_c2"]
    assert ret.get_property("my_foo") == ['bar', 'bar2']
    assert ret.get_property("my_foo2", "other_gen") == "bar2"

    # If we change the internal graph the order is different
    cppinfo.components["c1"].requires = []
    cppinfo.components["c2"].requires = ["c1"]

    ret = cppinfo.copy()
    ret.aggregate_components()

    assert ret.includedirs == ["includedir_c2", "includedir_c1"]
    assert ret.libdirs == ["libdir_c2", "libdir_c1"]
    assert ret.srcdirs == ["srcdir_c2", "srcdir_c1"]
    assert ret.bindirs == ["bindir_c2", "bindir_c1"]
    assert ret.builddirs == ["builddir_c2", "builddir_c1"]
    assert ret.frameworkdirs == ["frameworkdir_c2", "frameworkdir_c1"]


@pytest.mark.parametrize("aggregate_first", [True, False])
def test_cpp_info_merge_aggregating_components_first(aggregate_first):
    cppinfo = NewCppInfo()
    for n in _DIRS_VAR_NAMES + _FIELD_VAR_NAMES:
        setattr(cppinfo.components["foo"], n, ["var_{}_1".format(n), "var_{}_2".format(n)])
        setattr(cppinfo.components["foo2"], n, ["var2_{}_1".format(n), "var2_{}_2".format(n)])

    cppinfo.components["foo"].requires = ["foo2"]  # Deterministic order

    other = NewCppInfo()
    for n in _DIRS_VAR_NAMES + _FIELD_VAR_NAMES:
        setattr(other.components["boo"], n, ["jar_{}_1".format(n), "jar_{}_2".format(n)])
        setattr(other.components["boo2"], n, ["jar2_{}_1".format(n), "jar2_{}_2".format(n)])

    other.components["boo"].requires = ["boo2"]  # Deterministic order

    if aggregate_first:
        cppinfo.aggregate_components()
        other.aggregate_components()

    cppinfo.merge(other)

    if aggregate_first:
        for n in _DIRS_VAR_NAMES + _FIELD_VAR_NAMES:
            assert getattr(cppinfo, n) == ["var_{}_1".format(n), "var_{}_2".format(n),
                                           "var2_{}_1".format(n), "var2_{}_2".format(n),
                                           "jar_{}_1".format(n), "jar_{}_2".format(n),
                                           "jar2_{}_1".format(n), "jar2_{}_2".format(n)]
    else:
        for n in _DIRS_VAR_NAMES + _FIELD_VAR_NAMES:
            assert getattr(cppinfo.components["foo"], n) == ["var_{}_1".format(n),
                                                             "var_{}_2".format(n)]
            assert getattr(cppinfo.components["foo2"], n) == ["var2_{}_1".format(n),
                                                              "var2_{}_2".format(n)]
            assert getattr(cppinfo.components["boo"], n) == ["jar_{}_1".format(n),
                                                             "jar_{}_2".format(n)]
            assert getattr(cppinfo.components["boo2"], n) == ["jar2_{}_1".format(n),
                                                              "jar2_{}_2".format(n)]
            assert getattr(cppinfo, n) == None


def test_from_old_cppinfo_components():
    oldcppinfo = CppInfo("ref", "/root/")
    for n in _DIRS_VAR_NAMES + _FIELD_VAR_NAMES:
        setattr(oldcppinfo.components["foo"], n, ["var_{}_1".format(n), "var_{}_2".format(n)])
        setattr(oldcppinfo.components["foo2"], n, ["var2_{}_1".format(n), "var2_{}_2".format(n)])

    # The names and filenames are not copied to the new model
    oldcppinfo.components["foo"].names["Gen"] = ["MyName"]
    oldcppinfo.filenames["Gen"] = ["Myfilename"]
    oldcppinfo.components["foo"].build_modules = \
        {"cmake_find_package_multi": ["foo_my_scripts.cmake"],
         "cmake_find_package": ["foo.cmake"]}
    oldcppinfo.components["foo2"].build_modules = \
        {"cmake_find_package_multi": ["foo2_my_scripts.cmake"]}

    cppinfo = from_old_cppinfo(oldcppinfo)

    assert isinstance(cppinfo, NewCppInfo)

    for n in _DIRS_VAR_NAMES + _FIELD_VAR_NAMES:
        assert getattr(cppinfo.components["foo"], n) == ["var_{}_1".format(n),
                                                         "var_{}_2".format(n)]
        assert getattr(cppinfo.components["foo2"], n) == ["var2_{}_1".format(n),
                                                          "var2_{}_2".format(n)]

    assert cppinfo.components["foo"].get_property("cmake_build_modules") == \
           ["foo_my_scripts.cmake", "foo.cmake"]
    assert cppinfo.components["foo2"].get_property("cmake_build_modules") == \
           ["foo2_my_scripts.cmake"]


def test_from_old_cppinfo_no_components():
    oldcppinfo = CppInfo("ref", "/root/")
    for n in _DIRS_VAR_NAMES + _FIELD_VAR_NAMES:
        setattr(oldcppinfo, n, ["var_{}_1".format(n), "var_{}_2".format(n)])

    oldcppinfo.build_modules = {"cmake_find_package": ["my_scripts.cmake", "foo.cmake"],
                                "cmake_find_package_multi": ["my_scripts.cmake", "foo2.cmake"]}

    cppinfo = from_old_cppinfo(oldcppinfo)

    assert isinstance(cppinfo, NewCppInfo)

    for n in _DIRS_VAR_NAMES + _FIELD_VAR_NAMES:
        assert getattr(cppinfo, n) == ["var_{}_1".format(n), "var_{}_2".format(n)]

    assert cppinfo.get_property("cmake_build_modules") == ["my_scripts.cmake", "foo.cmake",
                                                           "foo2.cmake"]


def test_fill_old_cppinfo():
    """The source/build have priority unless it is not declared at all"""
    source = NewCppInfo()
    source.libdirs = ["source_libdir"]
    source.cxxflags = ["source_cxxflags"]
    build = NewCppInfo()
    build.libdirs = ["build_libdir"]
    build.frameworkdirs = []  # An empty list is an explicit delaration with priority too
    build.set_property("cmake_build_modules", ["my_cmake.cmake"])
    build.builddirs = ["my_build"]

    old_cpp = CppInfo("lib/1.0", "/root/folder")
    old_cpp.filter_empty = False
    old_cpp.libdirs = ["package_libdir"]
    old_cpp.cxxflags = ["package_cxxflags"]
    old_cpp.cflags = ["package_cflags"]
    old_cpp.frameworkdirs = ["package_frameworks"]

    full_editables = NewCppInfo()
    full_editables.merge(source)
    full_editables.merge(build)

    fill_old_cppinfo(full_editables, old_cpp)
    assert [e.replace("\\", "/") for e in old_cpp.lib_paths] == \
           ["/root/folder/source_libdir", "/root/folder/build_libdir"]
    assert old_cpp.cxxflags == ["source_cxxflags"]
    assert old_cpp.cflags == ["package_cflags"]
    assert old_cpp.frameworkdirs == []
    assert old_cpp.get_property("cmake_build_modules", "my_cmake.cmake")
    assert old_cpp.builddirs == ["my_build"]


def test_fill_old_cppinfo_simple():
    """ The previous test but simpler, just with one cppinfo simulating the package layout"""
    package_info = NewCppInfo()
    package_info.libs = []  # This is explicit declaration too
    package_info.includedirs = ["other_include"]

    old_cpp = CppInfo("lib/1.0", "/root/folder")
    old_cpp.filter_empty = False
    old_cpp.libs = ["this_is_discarded"]
    old_cpp.libdirs = ["package_libdir"]
    old_cpp.cxxflags = ["package_cxxflags"]
    old_cpp.cflags = ["package_cflags"]
    old_cpp.frameworkdirs = ["package_frameworks"]

    fill_old_cppinfo(package_info, old_cpp)
    assert [e.replace("\\", "/") for e in old_cpp.lib_paths] == \
           ["/root/folder/package_libdir"]
    assert old_cpp.cxxflags == ["package_cxxflags"]
    assert old_cpp.cflags == ["package_cflags"]
    assert old_cpp.frameworkdirs == ["package_frameworks"]
    assert old_cpp.libs == []
    assert old_cpp.includedirs == ["other_include"]
