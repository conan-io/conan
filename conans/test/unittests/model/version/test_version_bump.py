import pytest

from conans.model.version import Version

values = [
    ['1.0.0',       0, "2.0.0"],
    ['1.1.0',       0, "2.0.0"],
    ['1.1.1-pre',   0, "2.0.0"],
    ['1.1.1',       1, "1.2.0"],
    ['1.1.1',       2, "1.1.2"],
]


@pytest.mark.parametrize("version, index, result", values)
def test_version_bump(version, index, result):
    r = Version(version)
    bumped = r.bump(index)
    assert bumped == result
