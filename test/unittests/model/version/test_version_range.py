import textwrap

import pytest

from conans.errors import ConanException
from conans.model.version import Version
from conans.model.version_range import VersionRange
from conan.test.utils.tools import TestClient

values = [
    ['=1.0.0',  [[['=', '1.0.0']]],                   ["1.0.0"],          ["0.1"]],
    ['>1.0.0',  [[['>', '1.0.0']]],                   ["1.0.1"],          ["0.1"]],
    ['<2.0',    [[['<', '2.0-']]],                     ["1.0.1"],          ["2.1"]],
    ['>1 <2.0', [[['>', '1'], ['<', '2.0-']]],         ["1.5.1"],          ["0.1", "2.1"]],
    # tilde
    ['~2.5',    [[['>=', '2.5-'], ['<', '2.6-']]],      ["2.5.0", "2.5.3"], ["2.7", "2.6.1"]],
    ['~2.5.1',  [[['>=', '2.5.1-'], ['<', '2.6.0-']]],  ["2.5.1", "2.5.3"], ["2.5", "2.6.1"]],
    ['~1',      [[['>=', '1-'], ['<', '2-']]],          ["1.3", "1.8.1"],   ["0.8", "2.2"]],
    # caret
    ['^1.2',    [[['>=', '1.2-'], ['<', '2.0-']]],      ["1.2.1", "1.51"],  ["1", "2", "2.0.1"]],
    ['^1.2.3',	[[['>=', '1.2.3-'], ["<", '2.0.0-']]],  ["1.2.3", "1.2.4"], ["2", "2.1", "2.0.1"]],
    ['^0.1.2',  [[['>=', '0.1.2-'], ['<', '0.2.0-']]],  ["0.1.3", "0.1.44"], ["1", "0.3", "0.2.1"]],
    # Identity
    ['1.0.0',   [[["=", "1.0.0"]]],                   ["1.0.0"],          ["2", "1.0.1"]],
    ['=1.0.0',  [[["=", "1.0.0"]]],                   ["1.0.0"],          ["2", "1.0.1"]],
    # Any
    ['*',       [[[">=", "0.0.0-"]]],                  ["1.0", "a.b"],          []],
    ['',        [[[">=", "0.0.0-"]]],                  ["1.0", "a.b"],          []],
    # Unions
    ['1.0.0 || 2.1.3',  [[["=", "1.0.0"]], [["=", "2.1.3"]]],  ["1.0.0", "2.1.3"],  ["2", "1.0.1"]],
    ['>1 <2.0 || ^3.2 ',  [[['>', '1'], ['<', '2.0-']],
                           [['>=', '3.2-'], ['<', '4.0-']]],   ["1.5", "3.3"],  ["2.1", "0.1", "5"]],
    # pre-releases
    ['',                             [[[">=", "0.0.0-"]]],    ["1.0"],                ["1.0-pre.1"]],
    ['*, include_prerelease=True',   [[[">=", "0.0.0-"]]],    ["1.0", "1.0-pre.1", "0.0.0", "0.0.0-pre.1"],   []],
    ['>1- <2.0',                     [[['>', '1-'], ['<', '2.0-']]],
                                     ["1.0", "1.1", "1.9"],   ["1-pre.1", "1.5.1-pre1", "2.1-pre1"]],
    ['>1- <2.0 || ^3.2 ',  [[['>', '1-'], ['<', '2.0-']], [['>=', '3.2-'], ['<', '4.0-']]],
                           ["1.0", "1.2", "3.3"],  ["1-pre.1", "1.5-a1", "3.3-a1"]],
    ['^1.1.2',  [[['>=', '1.1.2-'], ['<', '2.0.0-']]], ["1.2.3"],  ["1.2.0-alpha1", "2.0.0-alpha1"]],
    ['^1.0.0, include_prerelease=True',  [[['>=', '1.0.0-'], ['<', '2.0.0-']]], ["1.2.3", "1.2.0-alpha1"],  ["2.0.0-alpha1"]],
    ['~1.1.2',  [[['>=', '1.1.2-'], ['<', '1.2.0-']]], ["1.1.3"],  ["1.1.3-alpha1", "1.2.0-alpha1"]],
    ['>=2.0-pre.0 <3', [[['>=', '2.0-pre.0'], ['<', '3-']]], ["2.1"], ["2.0-pre.1", "2.0-alpha.1"]],
    # Build metadata
    ['>=1.0.0+2', [[['>=', '1.0.0+2']]], ["1.0.0+2", "1.0.0+3"], ["1.0.0+1"]],
    ['>=1.0.0', [[['>=', '1.0.0-']]], ["1.0.0+2", "1.0.0+3"], []],
    # Build metadata and pre-releases
    ['>=1.0.0-pre.1+2', [[['>=', '1.0.0-pre.1+2']]], ["1.0.0+1", "1.0.0+2"], ["1.0.0-pre.1+3"]],  # excluded 1+3 because is a pre-release!
    ['>=1.0.0-pre.1+2, include_prerelease=True', [[['>=', '1.0.0-pre.1+2']]], ["1.0.0+1", "1.0.0+2", "1.0.0-pre.1+3"], ["1.0.0-pre.1+1"]],
    ['<1.0.1-pre.1+2', [[['<', '1.0.1-pre.1+2']]], ["1.0.0+1", "1.0.0+2"], ["1.0.0-pre.1+2"]],
    ['<1.0.1-pre.1+2, include_prerelease=True', [[['<', '1.0.1-pre.1+2']]], ["1.0.0+1", "1.0.0+2", "1.0.1-pre.1+1"], ["1.0.1-pre.1+2"]],
    # Or explicitly
    ['>=2.0-pre.0, include_prerelease', [[['>=', '2.0-pre.0']]], ["2.1", "2.0-pre.1"], ["1.5"]],
    # Build metadata
    ['>=1.0.0+2', [[['>=', '1.0.0+2']]], ["1.0.0+2", "1.0.0+3"], ["1.0.0+1"]],
    ['>=2.2.0+build.en.305 <2.2.0+build.en.306', [], ["2.2.0+build.en.305", "2.2.0+build.en.305.1", "2.2.0+build.en.305.2"], ["2.2.0+build.en.306"]]
]


@pytest.mark.parametrize("version_range, conditions, versions_in, versions_out", values)
def test_range(version_range, conditions, versions_in, versions_out):
    r = VersionRange(version_range)
    for condition_set, expected_condition_set in zip(r.condition_sets, conditions):
        for condition, expected_condition in zip(condition_set.conditions, expected_condition_set):
            assert condition.operator == expected_condition[0], f"Expected {r} condition operator to be {expected_condition[0]}, but got {condition.operator}"
            assert condition.version == expected_condition[1], f"Expected {r} condition version to be {expected_condition[1]}, but got {condition.version}"

    for v in versions_in:
        assert r.contains(Version(v), None), f"[{r}] must contain {v}"

    for v in versions_out:
        assert not r.contains(Version(v), None), f"[{r}] must not contain {v}"


@pytest.mark.parametrize("version_range, resolve_prereleases, versions_in, versions_out", [
    ['*', True, ["1.5.1", "1.5.1-pre1", "2.1-pre1"], []],
    ['*', False, ["1.5.1"], ["1.5.1-pre1", "2.1-pre1"]],
    ['*', None, ["1.5.1"], ["1.5.1-pre1", "2.1-pre1"]],

    ['*, include_prerelease', True, ["1.5.1", "1.5.1-pre1", "2.1-pre1"], []],
    ['*, include_prerelease', False, ["1.5.1"], ["1.5.1-pre1", "2.1-pre1"]],
    ['*, include_prerelease', None, ["1.5.1", "1.5.1-pre1", "2.1-pre1"], []],

    ['>1 <2.0', True, ["1.5.1", "1.5.1-pre1"], ["2.1-pre1"]],
    ['>1 <2.0', False, ["1.5.1"], ["1.5.1-pre1", "2.1-pre1"]],
    ['>1 <2.0', None, ["1.5.1"], ["1.5.1-pre1", "2.1-pre1"]],

    ['>1- <2.0', True, ["1.5.1", "1.5.1-pre1"], ["2.1-pre1"]],
    ['>1- <2.0', False, ["1.5.1"], ["1.5.1-pre1", "2.1-pre1"]],
    ['>1- <2.0, include_prerelease', None, ["1.5.1", "1.5.1-pre1"], ["2.1-pre1"]],

    ['>1 <2.0, include_prerelease', True, ["1.5.1", "1.5.1-pre1"], ["2.1-pre1"]],
    ['>1 <2.0, include_prerelease', False, ["1.5.1"], ["1.5.1-pre1", "2.1-pre1"]],
    ['>1 <2.0, include_prerelease', None, ["1.5.1", "1.5.1-pre1"], ["2.1-pre1"]],

    # Summary of new behaviors
    ['>=1 <2.0', False, ["1.0", "1.1", "1.9"], ["0.9", "1.0-pre.1", "1.1-pre.1", "2.0-pre", "2.0"]],
    # OLD
    # ['>=1 <2.0', True, ["1.0", "1.1-pre.1", "1.1", "1.9", "2.0-pre"], ["0.9", "1.0-pre.1", "2.0"]],
    # NEW
    ['>=1 <2.0', True, ["1.0-pre.1", "1.0", "1.1-pre.1", "1.1", "1.9"], ["0.9", "2.0", "2.0-pre"]],
    ['>1 <=2.0', False, ["1.1", "1.9", "2.0"], ["0.9", "1.0-pre.1", "1.0", "1.1-pre.1", "2.0-pre"]],
    # This should be old and new behaviors remain the same
    ['>1 <=2.0', True, ["1.1-pre.1", "1.1", "1.9", "2.0", "2.0-pre"], ["0.9", "1.0", "1.0-pre.1"]],
])
def test_range_prereleases_conf(version_range, resolve_prereleases, versions_in, versions_out):
    r = VersionRange(version_range)

    for v in versions_in:
        assert r.contains(Version(v), resolve_prereleases), f"Expected '{version_range}' to contain '{v}' (conf.ranges_resolve_prereleases={resolve_prereleases})"

    for v in versions_out:
        assert not r.contains(Version(v), resolve_prereleases), f"Expected '{version_range}' NOT to contain '{v}' (conf.ranges_resolve_prereleases={resolve_prereleases})"


@pytest.mark.parametrize("version_range", [
    ">= 1.0",  # https://github.com/conan-io/conan/issues/12692
    ">=0.0.1 < 1.0",  # https://github.com/conan-io/conan/issues/14612
    "==1.0",  "~=1.0",  "^=1.0", "v=1.0"  # https://github.com/conan-io/conan/issues/16066
])
def test_wrong_range_syntax(version_range):
    with pytest.raises(ConanException):
        VersionRange(version_range)


@pytest.mark.parametrize("version_range", [
    ">=0.1, include_prerelease",
    ">=0.1, include_prerelease=True",
    ">=0.1, include_prerelease=False",
])
def test_wrong_range_option_syntax(version_range):
    """We don't error out on bad options, maybe we should,
    but for now this test ensures we don't change it without realizing"""
    vr = VersionRange(version_range)
    assert all(cs.prerelease for cs in vr.condition_sets)


def test_version_range_error_ux():
    # https://github.com/conan-io/conan/issues/16288
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            requires = "mydep/[>1.0 < 3]"
        """)
    c.save({"conanfile.py": conanfile})
    c.run("install .", assert_error=True)
    assert "Recipe 'conanfile' requires 'mydep/[>1.0 < 3]' version-range definition error" in c.out
    c.run("export . --name=mypkg --version=0.1")
    c.run("install --requires=mypkg/0.1", assert_error=True)
    assert "Recipe 'mypkg/0.1' requires 'mydep/[>1.0 < 3]' version-range definition error" in c.out
