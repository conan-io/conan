from conans.model.build_info import CppInfo, CppInfoDefaultValues

names_dirs = ["lib", "include", "build", "bin", "framework", "res"]
names_vars = ["libs", "defines", "cflags", "cxxflags", "sharedlinkflags", "exelinkflags",
              "system_libs"]


def test_merge1_without_components():
    # Regular merge, in an object with a parent folder
    source = CppInfo("source", "/folder/source_folder", default_values=CppInfoDefaultValues())
    build = CppInfo("build", "/folder/build_folder", default_values=CppInfoDefaultValues())

    for var in names_dirs:
        setattr(source, "{}dirs".format(var), [var, "{}_source1".format(var), "{}_source2".format(var)])
        setattr(build, "{}dirs".format(var), [var, "{}_build1".format(var), "{}_build2".format(var)])

    agg = CppInfo("aggregated", "/folder", default_values=CppInfoDefaultValues())
    agg.merge(source)
    agg.merge(build)

    for var in names_dirs:
        values = getattr(agg, "{}dirs".format(var))
        assert values == ["source_folder/{}".format(var),
                          "source_folder/{}_source1".format(var),
                          "source_folder/{}_source2".format(var),
                          "build_folder/{}".format(var),
                          "build_folder/{}_build1".format(var),
                          "build_folder/{}_build2".format(var)]


def test_merge2_without_components():
    # Regular merge, when source and build shares a folder, the entries are not duplicated in
    # the list
    source = CppInfo("source", "/folder/build", default_values=CppInfoDefaultValues())
    build = CppInfo("build", "/folder/build", default_values=CppInfoDefaultValues())

    for var in names_dirs:
        setattr(source, "{}dirs".format(var), [var, "other_{}".format(var)])
        setattr(build, "{}dirs".format(var), [var, "other_{}".format(var)])

    agg = CppInfo("aggregated", "/folder", default_values=CppInfoDefaultValues())
    agg.merge(source)
    agg.merge(build)

    for var in names_dirs:
        values = getattr(agg, "{}dirs".format(var))
        assert values == ["build/{}".format(var),
                          "build/other_{}".format(var)]


def test_merge3_without_components():
    # Folder outside the parent folder
    source = CppInfo("source", "/folder/source", default_values=CppInfoDefaultValues())
    build = CppInfo("build", "/../build", default_values=CppInfoDefaultValues())

    for var in names_dirs:
        setattr(source, "{}dirs".format(var), [var, "other_{}".format(var)])
        setattr(build, "{}dirs".format(var), [var, "other_{}".format(var)])

    agg = CppInfo("aggregated", "/folder", default_values=CppInfoDefaultValues())
    agg.merge(source)
    agg.merge(build)

    for var in names_dirs:
        values = getattr(agg, "{}dirs".format(var))
        assert values == ["source/{}".format(var),
                          "source/other_{}".format(var),
                          "../build/{}".format(var),
                          "../build/other_{}".format(var)]


def test_merge1_components():
    # Folder outside the parent folder
    source = CppInfo("source", "/folder/source", default_values=CppInfoDefaultValues())
    build = CppInfo("build", "/folder/build", default_values=CppInfoDefaultValues())

    for var in names_dirs:
        setattr(source.components["c1"], "{}dirs".format(var), [var, "other_{}".format(var)])
        setattr(build.components["c1"], "{}dirs".format(var), [var, "other_{}".format(var)])

    agg = CppInfo("aggregated", "/folder", default_values=CppInfoDefaultValues())
    agg.merge(source)
    agg.merge(build)

    for var in names_dirs:
        values = getattr(agg.components["c1"], "{}dirs".format(var))
        assert values == ["source/{}".format(var),
                          "source/other_{}".format(var),
                          "build/{}".format(var),
                          "build/other_{}".format(var)]


def test_merge2_components():
    # Folder outside the parent folder
    source = CppInfo("source", "/folder/source", default_values=CppInfoDefaultValues())
    build = CppInfo("build", "/../build", default_values=CppInfoDefaultValues())

    for var in names_dirs:
        setattr(source.components["c1"], "{}dirs".format(var), [var, "other_{}".format(var)])
        setattr(build.components["c1"], "{}dirs".format(var), [var, "other_{}".format(var)])

    agg = CppInfo("aggregated", "/folder", default_values=CppInfoDefaultValues())
    agg.merge(source)
    agg.merge(build)

    for var in names_dirs:
        values = getattr(agg.components["c1"], "{}dirs".format(var))
        assert values == ["source/{}".format(var),
                          "source/other_{}".format(var),
                          "../build/{}".format(var),
                          "../build/other_{}".format(var)]


def test_vars_are_merged_without_components():
    # The "libs", "cxxflags" and other vars are merged too
    source = CppInfo("source", "/folder/source_folder", default_values=CppInfoDefaultValues())
    build = CppInfo("build", "/folder/build_folder", default_values=CppInfoDefaultValues())

    for var in names_vars:
        setattr(source, var, ["value_{}_source".format(var)])
        setattr(build, var, ["value_{}_build".format(var)])

    agg = CppInfo("aggregated", "/folder", default_values=CppInfoDefaultValues())
    agg.merge(source)
    agg.merge(build)

    for var in names_vars:
        values = getattr(agg, var)
        assert values == ["value_{}_source".format(var), "value_{}_build".format(var)]


def test_vars_are_merged_components():
    # Folder outside the parent folder
    source = CppInfo("source", "/folder/source", default_values=CppInfoDefaultValues())
    build = CppInfo("build", "/../build", default_values=CppInfoDefaultValues())

    for var in names_vars:
        setattr(source.components["c1"], var, ["value_{}_source".format(var)])
        setattr(build.components["c1"], var, ["value_{}_build".format(var)])

    agg = CppInfo("aggregated", "/folder", default_values=CppInfoDefaultValues())
    agg.merge(source)
    agg.merge(build)

    for var in names_vars:
        values = getattr(agg.components["c1"], var)
        assert values == ["value_{}_source".format(var), "value_{}_build".format(var)]
