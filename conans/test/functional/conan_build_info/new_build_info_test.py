import pytest

from conans.errors import ConanException
from conans.model.build_info import CppInfo
from conans.model.new_build_info import NewCppInfo, _DIRS_VAR_NAMES, _FIELD_VAR_NAMES


def test_components_order():
    cppinfo = NewCppInfo()
    cppinfo.components["c1"].requires = ["c4", "OtherPackage::OtherComponent2"]
    cppinfo.components["c2"].requires = ["OtherPackage::OtherComponent"]
    cppinfo.components["c3"].requires = ["c2"]
    cppinfo.components["c4"].requires = ["c3"]
    sorted_c = list(cppinfo.get_sorted_components().keys())
    assert sorted_c == ["c2", "c3", "c4", "c1"]


def test_names_filenames():
    cppinfo = NewCppInfo()
    cppinfo.names["generator1"] = "name1"
    cppinfo.names["generator2"] = "name2"
    cppinfo.filenames["generator1"] = "name_file"

    assert cppinfo.get_name("generator1") == "name1"
    assert cppinfo.get_filename("generator1") == "name_file"
    assert cppinfo.get_filename("generator2") == "name2"

    assert cppinfo.get_filename("missing") is None
    assert cppinfo.get_name("missing") is None


def test_component_aggregation():
    cppinfo = NewCppInfo()
    cppinfo.build_modules["foo"] = ["var1" ,"var2", "var3"]
    cppinfo.names["generator1"] = "name1"
    cppinfo.names["generator2"] = "name2"
    cppinfo.filenames["generator1"] = "name_file"

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

    cppinfo.components["c1"].requires = ["c2", "LIB_A::C1"]
    cppinfo.components["c1"].includedirs = ["includedir_c1"]
    cppinfo.components["c1"].libdirs = ["libdir_c1"]
    cppinfo.components["c1"].srcdirs = ["srcdir_c1"]
    cppinfo.components["c1"].bindirs = ["bindir_c1"]
    cppinfo.components["c1"].builddirs = ["builddir_c1"]
    cppinfo.components["c1"].frameworkdirs = ["frameworkdir_c1"]
    cppinfo.components["c1"].cxxflags = ["cxxflags_c1"]
    cppinfo.components["c1"].defines = ["defines_c1"]

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


def norm(paths):
    return [d.replace("\\", "/") for d in paths]


def test_cpp_info_merge_with_components():
    """If we try to merge a cpp info with another one and some of them have components, assert"""
    cppinfo = NewCppInfo()
    cppinfo.components["foo"].cxxflags = ["var"]

    other = NewCppInfo()
    other.components["foo2"].cxxflags = ["var2"]

    with pytest.raises(ConanException) as exc:
        cppinfo.merge(other)

    assert "Cannot aggregate two cppinfo objects with components" in str(exc.value)


def test_cpp_info_merge_aggregating_components_first():
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

    cppinfo.aggregate_components()
    other.aggregate_components()

    cppinfo.merge(other)

    for n in _DIRS_VAR_NAMES + _FIELD_VAR_NAMES:
        assert getattr(cppinfo, n) == ["var_{}_1".format(n), "var_{}_2".format(n),
                                       "var2_{}_1".format(n), "var2_{}_2".format(n),
                                       "jar_{}_1".format(n), "jar_{}_2".format(n),
                                       "jar2_{}_1".format(n), "jar2_{}_2".format(n)]


def test_from_old_cppinfo_components():
    oldcppinfo = CppInfo("ref", "/root/")
    for n in _DIRS_VAR_NAMES + _FIELD_VAR_NAMES:
        setattr(oldcppinfo.components["foo"], n, ["var_{}_1".format(n), "var_{}_2".format(n)])
        setattr(oldcppinfo.components["foo2"], n, ["var2_{}_1".format(n), "var2_{}_2".format(n)])

    oldcppinfo.components["foo"].names["Gen"] = ["MyName"]
    oldcppinfo.filenames["Gen"] = ["Myfilename"]

    cppinfo = NewCppInfo.from_old_cppinfo(oldcppinfo)

    assert isinstance(cppinfo, NewCppInfo)

    for n in _DIRS_VAR_NAMES + _FIELD_VAR_NAMES:
        assert getattr(cppinfo.components["foo"], n) == ["var_{}_1".format(n),
                                                         "var_{}_2".format(n)]
        assert getattr(cppinfo.components["foo2"], n) == ["var2_{}_1".format(n),
                                                          "var2_{}_2".format(n)]

    assert cppinfo.components["foo"].names["Gen"] == ["MyName"]
    assert cppinfo.filenames["Gen"] == ["Myfilename"]


def test_from_old_cppinfo_no_components():
    oldcppinfo = CppInfo("ref", "/root/")
    for n in _DIRS_VAR_NAMES + _FIELD_VAR_NAMES:
        setattr(oldcppinfo, n, ["var_{}_1".format(n), "var_{}_2".format(n)])

    cppinfo = NewCppInfo.from_old_cppinfo(oldcppinfo)

    assert isinstance(cppinfo, NewCppInfo)

    for n in _DIRS_VAR_NAMES + _FIELD_VAR_NAMES:
        assert getattr(cppinfo, n) == ["var_{}_1".format(n), "var_{}_2".format(n)]
