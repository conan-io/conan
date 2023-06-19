import pytest

from conans.model.version import Version

v = [("1.2.3",
      (1, 2, 3), None, None),
     ("master+build2",
      ['master'], None, "build2"),
     ("1.2.3-alpha1+build2",
      (1, 2, 3), "alpha1", "build2"),
     ("1.2.3+build2",
      (1, 2, 3), None, "build2"),
     ("",
      [''], None, None),
     ("+build2",
      [''], None, "build2"),
     ("1.2.3b.4-pre.1.2b+build.1.1b",
      (1, 2, "3b", 4), "pre.1.2b", "build.1.1b"),
     ("0.2.3+b178",
      (0, 2, 3), None, "b178"),
     ("1.2.3.4.5",
      (1, 2, 3, 4, 5), None, None)
     ]


@pytest.mark.parametrize("v_str, main, build, pre", v)
def test_parse(v_str, main, build, pre):
    v1 = Version(v_str)
    assert len(v1.main) == len(main)
    for v_i, v_i_e in zip(v1.main, main):
        assert v_i == v_i_e
    assert v1.pre == build
    assert v1.build == pre
    assert str(v1) == v_str
