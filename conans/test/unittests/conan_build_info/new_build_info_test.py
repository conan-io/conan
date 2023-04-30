import pytest

from conans.model.build_info import CppInfo, _DIRS_VAR_NAMES, _FIELD_VAR_NAMES


def test_components_order():
    cppinfo = CppInfo()
    cppinfo.components["c1"].requires = ["c4", "OtherPackage::OtherComponent2"]
    cppinfo.components["c2"].requires = ["OtherPackage::OtherComponent"]
    cppinfo.components["c3"].requires = ["c2"]
    cppinfo.components["c4"].requires = ["c3"]
    sorted_c = list(cppinfo.get_sorted_components().keys())
    assert sorted_c == ["c2", "c3", "c4", "c1"]


def test_component_aggregation():
    cppinfo = CppInfo()

    cppinfo.includedirs = ["includedir"]
    cppinfo.libdirs = ["libdir"]
    cppinfo.srcdirs = ["srcdir"]
    cppinfo.bindirs = ["bindir"]
    cppinfo.builddirs = ["builddir"]
    cppinfo.frameworkdirs = ["frameworkdir"]
    cppinfo.set_property("foo", "bar")

    cppinfo.components["c2"].includedirs = ["includedir_c2"]
    cppinfo.components["c2"].libdirs = ["libdir_c2"]
    cppinfo.components["c2"].srcdirs = ["srcdir_c2"]
    cppinfo.components["c2"].bindirs = ["bindir_c2"]
    cppinfo.components["c2"].builddirs = ["builddir_c2"]
    cppinfo.components["c2"].frameworkdirs = ["frameworkdir_c2"]
    cppinfo.components["c2"].cxxflags = ["cxxflags_c2"]
    cppinfo.components["c2"].defines = ["defines_c2"]
    cppinfo.components["c2"].set_property("my_foo", ["bar", "bar2"])
    cppinfo.components["c2"].set_property("cmake_build_modules", ["build_module_c2",
                                                                  "build_module_c22"])

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
    cppinfo.components["c1"].set_property("my_foo2", "bar2")

    ret = cppinfo.aggregated_components()

    assert ret.get_property("foo") == "bar"
    assert ret.includedirs == ["includedir_c1", "includedir_c2"]
    assert ret.libdirs == ["libdir_c1", "libdir_c2"]
    assert ret.srcdirs == ["srcdir_c1", "srcdir_c2"]
    assert ret.bindirs == ["bindir_c1", "bindir_c2"]
    assert ret.builddirs == ["builddir_c1", "builddir_c2"]
    assert ret.frameworkdirs == ["frameworkdir_c1", "frameworkdir_c2"]
    assert ret.cxxflags == ["cxxflags_c1", "cxxflags_c2"]
    assert ret.defines == ["defines_c1", "defines_c2"]
    # The properties are not aggregated because we cannot generalize the meaning of a property
    # that belongs to a component, it could make sense to aggregate it or not, "cmake_target_name"
    # for example, cannot be aggregated. But "cmake_build_modules" is aggregated.
    assert ret.get_property("my_foo") is None
    assert ret.get_property("my_foo2") is None
    assert ret.get_property("cmake_build_modules") == None

    # If we change the internal graph the order is different
    cppinfo.components["c1"].requires = []
    cppinfo.components["c2"].requires = ["c1"]

    cppinfo._aggregated = None  # Dirty, just to force recomputation
    ret = cppinfo.aggregated_components()

    assert ret.includedirs == ["includedir_c2", "includedir_c1"]
    assert ret.libdirs == ["libdir_c2", "libdir_c1"]
    assert ret.srcdirs == ["srcdir_c2", "srcdir_c1"]
    assert ret.bindirs == ["bindir_c2", "bindir_c1"]
    assert ret.builddirs == ["builddir_c2", "builddir_c1"]
    assert ret.frameworkdirs == ["frameworkdir_c2", "frameworkdir_c1"]


def test_cpp_info_sysroot_merge():
    # If the value was already set is kept in the merge
    one = CppInfo()
    one.sysroot = "sys1"
    two = CppInfo()
    two.sysroot = "sys2"
    one.merge(two)
    assert one.sysroot == "sys1"

    # If the value was not set it is assigned
    one = CppInfo()
    two = CppInfo()
    two.sysroot = "sys2"
    one.merge(two)
    assert one.sysroot == "sys2"


@pytest.mark.parametrize("aggregate_first", [True, False])
def test_cpp_info_merge_aggregating_components_first(aggregate_first):
    cppinfo = CppInfo()
    for n in _DIRS_VAR_NAMES + _FIELD_VAR_NAMES:
        setattr(cppinfo.components["foo"], n, ["var_{}_1".format(n), "var_{}_2".format(n)])
        setattr(cppinfo.components["foo2"], n, ["var2_{}_1".format(n), "var2_{}_2".format(n)])

    cppinfo.components["foo"].requires = ["foo2"]  # Deterministic order

    other = CppInfo()
    for n in _DIRS_VAR_NAMES + _FIELD_VAR_NAMES:
        setattr(other.components["boo"], n, ["jar_{}_1".format(n), "jar_{}_2".format(n)])
        setattr(other.components["boo2"], n, ["jar2_{}_1".format(n), "jar2_{}_2".format(n)])

    other.components["boo"].requires = ["boo2"]  # Deterministic order

    if aggregate_first:
        cppinfo = cppinfo.aggregated_components()
        other = other.aggregated_components()

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
