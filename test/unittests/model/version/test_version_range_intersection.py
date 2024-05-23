import pytest

from conans.model.version_range import VersionRange

values = [
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
    # prereleases
    ['>1.0', ">1.0-", ">1.0"],
    ['>=1.0- <3.0', ">=1.0 <3.0-", ">=1.0 <3.0-"],
    ['>=1.0 <=3.0-', "<3", ">=1.0 <3"],
    # OR
    ['>=1.0 <2.0 || >=2.1 <3', ">=2.3", ">=2.3 <3"],
    ['>=1.3 <=1.9 || >2.1', ">=1.1 <=2.0 || >=2.1 <2.6", ">=1.3 <=1.9 || >2.1 <2.6"],
    ['>=1.3 <=1.9 || >=2.2', ">=1.8- <2.3 || >=2.1 <2.6", ">=1.8- <=1.9 || >=2.2 <2.3 || >=2.2 <2.6"],
]


@pytest.mark.parametrize("range1, range2, result", values)
def test_range_intersection(range1, range2, result):
    r1 = VersionRange(range1)
    r2 = VersionRange(range2)
    inter = r1.intersection(r2)
    result = f"[{result}]"
    assert inter.version() == result
    inter = r2.intersection(r1)  # Test reverse order, result should be the same
    assert inter.version() == result


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
