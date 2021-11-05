import pytest

from conans.model.recipe_ref import Version
from conans.model.version_range import VersionRange

values = [
    ['>1.0.0',  [['>', '1.0.0']],                   ["1.0.1"],  ["0.1"]],
    ['<2.0',    [['<', '2.0']],                     ["1.0.1"],  ["2.1"]],
    ['>1 <2.0', [['>', '1'], ['<', '2.0']],         ["1.5.1"],  ["0.1", "2.1"]],
]


@pytest.mark.parametrize("version_range, conditions, versions_in, versions_out", values)
def test_range(version_range, conditions, versions_in, versions_out):
    r = VersionRange(version_range)
    for result, expected in zip(r.conditions, conditions):
        assert result.operator == expected[0]
        assert result.version == expected[1]

    for v in versions_in:
        assert Version(v) in r

    for v in versions_out:
        assert Version(v) not in r
