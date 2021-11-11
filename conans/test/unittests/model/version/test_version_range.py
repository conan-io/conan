import pytest

from conans.errors import ConanException
from conans.model.recipe_ref import Version
from conans.model.version_range import VersionRange

values = [
    ['>1.0.0',  [['>', '1.0.0']],                   ["1.0.1"],          ["0.1"]],
    ['<2.0',    [['<', '2.0']],                     ["1.0.1"],          ["2.1"]],
    ['>1 <2.0', [['>', '1'], ['<', '2.0']],         ["1.5.1"],          ["0.1", "2.1"]],
    ['~2.5',    [['>=', '2.5'], ['<', '2.6']],      ["2.5.0", "2.5.3"], ["2.7", "2.6.1"]],
    ['~2.5.1',  [['>=', '2.5.1'], ['<', '2.6.0']],  ["2.5.1", "2.5.3"], ["2.5", "2.6.1"]],
    ['^1.2',    [['>=', '1.2'], ['<', '2.0']],      ["1.2.1", "1.51"],  ["1", "2.1", "2.0.1"]],
    ['^0.1.2',  [['>=', '0.1.2'], ['<', '0.2.0']],  ["0.1.3", "0.1.44"], ["1", "0.3", "0.2.1"]],
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


invalid = ["1.2", "-2.0", "?2.1"]


@pytest.mark.parametrize("version_range", invalid)
def test_invalid_range(version_range):
    with pytest.raises(ConanException) as e:
        VersionRange(version_range)
    assert "Invalid version range" in str(e.value)
