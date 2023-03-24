import pytest

from conans.errors import ConanException
from conans.model.recipe_ref import Version
from conans.model.version_range import VersionRange

values = [
    ['>1.0.0',  [[['>', '1.0.0']]],                   ["1.0.1"],          ["0.1"]],
    ['<2.0',    [[['<', '2.0']]],                     ["1.0.1"],          ["2.1"]],
    ['>1 <2.0', [[['>', '1'], ['<', '2.0']]],         ["1.5.1"],          ["0.1", "2.1"]],
    # tilde
    ['~2.5',    [[['>=', '2.5'], ['<', '2.6-']]],      ["2.5.0", "2.5.3"], ["2.7", "2.6.1"]],
    ['~2.5.1',  [[['>=', '2.5.1'], ['<', '2.6.0-']]],  ["2.5.1", "2.5.3"], ["2.5", "2.6.1"]],
    ['~1',      [[['>=', '1'], ['<', '2-']]],          ["1.3", "1.8.1"],   ["0.8", "2.2"]],
    # caret
    ['^1.2',    [[['>=', '1.2'], ['<', '2.0-']]],      ["1.2.1", "1.51"],  ["1", "2", "2.0.1"]],
    ['^1.2.3',	[[['>=', '1.2.3'], ["<", '2.0.0-']]],  ["1.2.3", "1.2.4"], ["2", "2.1", "2.0.1"]],
    ['^0.1.2',  [[['>=', '0.1.2'], ['<', '0.2.0-']]],  ["0.1.3", "0.1.44"], ["1", "0.3", "0.2.1"]],
    # Identity
    ['1.0.0',   [[["=", "1.0.0"]]],                   ["1.0.0"],          ["2", "1.0.1"]],
    ['=1.0.0',  [[["=", "1.0.0"]]],                   ["1.0.0"],          ["2", "1.0.1"]],
    # Any
    ['*',       [[[">=", "0.0.0"]]],                  ["1.0", "a.b"],          []],
    ['',        [[[">=", "0.0.0"]]],                  ["1.0", "a.b"],          []],
    # Unions
    ['1.0.0 || 2.1.3',  [[["=", "1.0.0"]], [["=", "2.1.3"]]],  ["1.0.0", "2.1.3"],  ["2", "1.0.1"]],
    ['>1 <2.0 || ^3.2 ',  [[['>', '1'], ['<', '2.0']],
                           [['>=', '3.2'], ['<', '4.0-']]],    ["1.5", "3.3"],  ["2.1", "0.1", "5"]],
    # pre-releases
    ['',                             [[[">=", "0.0.0"]]],    ["1.0"],                ["1.0-pre.1"]],
    ['*, include_prerelease=True',   [[[">=", "0.0.0"]]],    ["1.0", "1.0-pre.1"],   []],
    ['*-',                           [[[">=", "0.0.0"]]],    ["1.0", "1.0-pre.1"],   []],
    ['>1- <2.0',                     [[['>', '1'], ['<', '2.0']]], ["1.5.1-pre1"],   ["2.1-pre1"]],
    ['>1- <2.0 || ^3.2 ',  [[['>', '1'], ['<', '2.0']],
                            [['>=', '3.2'], ['<', '4.0-']]],   ["1.5-a1", "3.3"],  ["3.3-a1"]],
    ['^1.1.2-',  [[['>=', '1.1.2'], ['<', '2.0.0-']]], ["1.2.3", "1.2.0-alpha1"],  ["2.0.0-alpha1"]],
    ['~1.1.2-',  [[['>=', '1.1.2'], ['<', '1.2.0-']]], ["1.1.3", "1.1.3-alpha1"],  ["1.2.0-alpha1"]],
]


@pytest.mark.parametrize("version_range, conditions, versions_in, versions_out", values)
def test_range(version_range, conditions, versions_in, versions_out):
    r = VersionRange(version_range)
    for condition_set, expected_condition_set in zip(r.condition_sets, conditions):
        for condition, expected_condition in zip(condition_set.conditions, expected_condition_set):
            assert condition.operator == expected_condition[0]
            assert condition.version == expected_condition[1]

    for v in versions_in:
        assert r.contains(Version(v), None)

    for v in versions_out:
        assert not r.contains(Version(v), None)


@pytest.mark.parametrize("version_range, resolve_prereleases, versions_in, versions_out", [
    ['*', True, ["1.5.1", "1.5.1-pre1", "2.1-pre1"], []],
    ['*', False, ["1.5.1"], ["1.5.1-pre1", "2.1-pre1"]],
    ['*', None, ["1.5.1"], ["1.5.1-pre1", "2.1-pre1"]],

    ['*-', True, ["1.5.1", "1.5.1-pre1", "2.1-pre1"], []],
    ['*-', False, ["1.5.1"], ["1.5.1-pre1", "2.1-pre1"]],
    ['*-', None, ["1.5.1", "1.5.1-pre1", "2.1-pre1"], []],

    ['*, include_prerelease', True, ["1.5.1", "1.5.1-pre1", "2.1-pre1"], []],
    ['*, include_prerelease', False, ["1.5.1"], ["1.5.1-pre1", "2.1-pre1"]],
    ['*, include_prerelease', None, ["1.5.1", "1.5.1-pre1", "2.1-pre1"], []],

    ['>1 <2.0', True, ["1.5.1", "1.5.1-pre1"], ["2.1-pre1"]],
    ['>1 <2.0', False, ["1.5.1"], ["1.5.1-pre1", "2.1-pre1"]],
    ['>1 <2.0', None, ["1.5.1"], ["1.5.1-pre1", "2.1-pre1"]],

    ['>1- <2.0', True, ["1.5.1", "1.5.1-pre1"], ["2.1-pre1"]],
    ['>1- <2.0', False, ["1.5.1"], ["1.5.1-pre1", "2.1-pre1"]],
    ['>1- <2.0', None, ["1.5.1", "1.5.1-pre1"], ["2.1-pre1"]],

    ['>1 <2.0, include_prerelease', True, ["1.5.1", "1.5.1-pre1"], ["2.1-pre1"]],
    ['>1 <2.0, include_prerelease', False, ["1.5.1"], ["1.5.1-pre1", "2.1-pre1"]],
    ['>1 <2.0, include_prerelease', None, ["1.5.1", "1.5.1-pre1"], ["2.1-pre1"]],
])
def test_range_prereleases_conf(version_range, resolve_prereleases, versions_in, versions_out):
    r = VersionRange(version_range)

    for v in versions_in:
        assert r.contains(Version(v), resolve_prereleases), f"Expected '{version_range}' to contain '{v}' (conf.ranges_resolve_prereleases={resolve_prereleases})"

    for v in versions_out:
        assert not r.contains(Version(v), resolve_prereleases), f"Expected '{version_range}' NOT to contain '{v}' (conf.ranges_resolve_prereleases={resolve_prereleases})"


def test_wrong_range_syntax():
    # https://github.com/conan-io/conan/issues/12692
    with pytest.raises(ConanException):
        VersionRange(">= 1.0")
