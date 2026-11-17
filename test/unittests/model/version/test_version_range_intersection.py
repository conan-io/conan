import pytest

from conan.internal.model.version import Version
from conan.internal.model.version_range import VersionRange

values = [
    # any ranges
    ['*', "*", ">=0.0.0"],
    ['*', ">1.0", ">1.0"],
    ['*', "<2.0", ">=0.0.0 <2.0"],
    ['*', ">=1.0 <2.0", ">=1.0 <2.0"],
    # single lower limits bounds
    ['>1.0', ">1.0", ">1.0"],
    ['>=1.0', ">1.0", ">1.0"],
    ['>1.0', ">1.1", ">1.1"],
    ['>1.0', ">=1.1", ">=1.1"],
    ['>=1.0', ">=1.1", ">=1.1"],
    # single upper limits bounds
    ['<2.0', "<2.0", "<2.0"],
    ['<=1.0', "<1.0", "<1.0"],
    ['<2.0', "<2.1", "<2.0"],
    ['<2.0', "<=1.1", "<=1.1"],
    ['<=1.0', "<=1.1", "<=1.0"],
    # One lower limit, one upper
    ['>=1.0', "<2.0", ">=1.0 <2.0"],
    ['>=1', '<=1', ">=1 <=1"],
    [">=1", "<=1-", ">=1 <=1-"],
    [">=1-", "<=1", ">=1- <=1"],
    # Two lower, one upper
    ['>=1.0', ">1.0 <2.0", ">1.0 <2.0"],
    ['>=1.0', ">1.1 <2.0", ">1.1 <2.0"],
    ['>1.0', ">1.1 <=2.0", ">1.1 <=2.0"],
    ['>1.0', ">=1.1 <=2.0", ">=1.1 <=2.0"],
    # one lower, two upper
    ['<3.0', ">1.0 <2.0", ">1.0 <2.0"],
    ['<=2.0', ">1.1 <2.0", ">1.1 <2.0"],
    ['<1.9', ">1.1 <=2.0", ">1.1 <1.9"],
    ['<=1.9', ">=1.1 <=2.0", ">=1.1 <=1.9"],
    # two lower, two upper
    ['>0.1 <3.0', ">1.0 <2.0", ">1.0 <2.0"],
    ['>1.2 <=2.0', ">1.1 <2.0", ">1.2 <2.0"],
    ['>0.1 <1.9', ">1.1 <=2.0", ">1.1 <1.9"],
    ['>=1.3 <=1.9', ">=1.1 <=2.0", ">=1.3 <=1.9"],
    ['>=1.0 <=5.0', ">2 <2.5", ">2 <2.5"],
    # equal limits
    ['>=1.0 <3.0', ">0.0 <=1.0", ">=1.0 <=1.0"],
    # Empty ranges
    ['>1.0 <2.0', ">2.0 <3.0", None],
    ['>1.0 <2.0', ">2.0 <=3.0", None],
    ['>1.0 <2.0', ">=2.0.1 <3.0", None],
    ['>1.0 <2.0', ">3.0", None],
    # prereleases
    ['>1.0', ">1.0-", ">1.0"],
    ['>=1.0- <3.0', ">=1.0 <3.0-", ">=1.0 <3.0-"],
    ['>=1.0 <=3.0-', "<3", ">=1.0 <3"],
    # OR
    ['*', ">=1.0 <2.0 || >=3.0 <4.0", ">=1.0 <2.0 || >=3.0 <4.0"],
    ['>=1.0 <2.0 || >=2.1 <3', ">=2.3", ">=2.3 <3"],
    ['>=1.3 <=1.9 || >2.1', ">=1.1 <=2.0 || >=2.1 <2.6", ">=1.3 <=1.9 || >2.1 <2.6"],
    ['>=1.3 <=1.9 || >=2.2', ">=1.8- <2.3 || >=2.1 <2.6", ">=1.8- <=1.9 || >=2.2 <2.3 || >=2.2 <2.6"],
]


def _check_intersection(inter, result):
    if result is None:
        assert inter is None
        return
    assert inter.version() == f"[{result}]"
    # The condition sets of the intersection must be the same as parsing the resulting expression,
    # otherwise contains() on the intersection would behave differently than the expression says
    expected = VersionRange(result)
    assert len(inter.condition_sets) == len(expected.condition_sets)
    for cs, expected_cs in zip(inter.condition_sets, expected.condition_sets):
        assert cs.prerelease == expected_cs.prerelease
        assert [(c.operator, c.version) for c in cs.conditions] == \
               [(c.operator, c.version) for c in expected_cs.conditions]


@pytest.mark.parametrize("range1, range2, result", values)
def test_range_intersection(range1, range2, result):
    r1 = VersionRange(range1)
    r2 = VersionRange(range2)
    _check_intersection(r1.intersection(r2), result)
    # Test reverse order, result should be the same
    _check_intersection(r2.intersection(r1), result)


@pytest.mark.parametrize("range1, range2, versions_in, versions_out", [
    ['>1 <2', ">1.5", ["1.6", "1.9.9"], ["1.0", "1.5", "2.0", "2.5"]],
    ['>=1.0 <3.0', ">0.0 <=1.0", ["1.0"], ["0.9", "1.0.1"]],
    ['>=1.0 <2.0 || >=2.1 <3', ">=2.3", ["2.3", "2.9"], ["1.5", "2.2", "3.0"]],
    ['>=1.0- <2.0, include_prerelease', ">=1.5- <3.0, include_prerelease",
     ["1.5", "1.6-pre.1"], ["1.4", "2.0-pre.1", "2.0"]],
    ['>=1.0- <2.0, include_prerelease', ">=1.5- <3.0", ["1.5"], ["1.4", "1.6-pre.1", "2.0"]],
])
def test_range_intersection_contains(range1, range2, versions_in, versions_out):
    for inter in (VersionRange(range1).intersection(VersionRange(range2)),
                  VersionRange(range2).intersection(VersionRange(range1))):
        for v in versions_in:
            assert inter.contains(Version(v), None), f"{inter} must contain {v}"
        for v in versions_out:
            assert not inter.contains(Version(v), None), f"{inter} must not contain {v}"


incompatible_values = [
    ['>1.0', "<1.0"],
    ['>=1.0', "<1.0"],
    ['>1.0', "<=1.0"],
    ['>1.0 <2.0', ">2.0"],
    ['>1.0 <2.0', "<1.0"],
    ['>1.0 <2.0', ">3.0 <4.0"],
    ['<1.0', ">3.0 <4.0"],
    ['>=1.0 <2 || >2 <3', ">4 <5"]
]


@pytest.mark.parametrize("range1, range2", incompatible_values)
def test_range_intersection_incompatible(range1, range2):
    r1 = VersionRange(range1)
    r2 = VersionRange(range2)
    inter = r1.intersection(r2)
    assert inter is None
    inter = r2.intersection(r1)  # Test reverse order, result should be the same
    assert inter is None


prerelease_values = [
    [", include_prerelease",
     ">=1.0-pre.1 <1.0-pre.99, include_prerelease",
     ">=1.0-pre.1 <1.0-pre.99, include_prerelease"],
    [">=1.0-pre.1 <1.0-pre.99, include_prerelease",
     ">=1.0-pre.1 <1.0-pre.99, include_prerelease",
     ">=1.0-pre.1 <1.0-pre.99, include_prerelease"],
    [">=1.0-pre.1 <1.0-pre.99, include_prerelease",
     ">=1.0-pre.12 <1.0-pre.98, include_prerelease",
     ">=1.0-pre.12 <1.0-pre.98, include_prerelease"],
    [">=1.0-pre.12 <1.0-pre.99, include_prerelease",
     ">=1.0-pre.1 <1.0-pre.98, include_prerelease",
     ">=1.0-pre.12 <1.0-pre.98, include_prerelease"],
    [">=1.0-pre.1 <1.0-pre.99",
     ">=1.0-pre.1 <1.0-pre.99, include_prerelease",
     ">=1.0-pre.1 <1.0-pre.99"],
    [">=1.0-pre.1 <1.0-pre.99, include_prerelease",
     ">=1.0-pre.12 <1.0-pre.98",
     ">=1.0-pre.12 <1.0-pre.98"],
    [">=1.0-pre.12 <1.0-pre.99",
     ">=1.0-pre.1 <1.0-pre.98",
     ">=1.0-pre.12 <1.0-pre.98"]
]


@pytest.mark.parametrize("range1, range2, result", prerelease_values)
def test_range_intersection_prerelease(range1, range2, result):
    r1 = VersionRange(range1)
    r2 = VersionRange(range2)
    _check_intersection(r1.intersection(r2), result)
    # Test reverse order, result should be the same
    _check_intersection(r2.intersection(r1), result)
