import pytest

from conans.model.version import Version

v = [("1.2.3",
      (1, 2, 3, None), None, None),
     ("master+build2",
      ("master", None, None, None), None, "build2"),
     ("1.2.3-alpha1+build2",
      (1, 2, 3, None), "alpha1", "build2"),
     ("1.2.3+build2",
      (1, 2, 3, None), None, "build2"),
     ("+build2",
      (None, None, None, None), None, "build2"),
     ("1.2.3b.4-pre.1.2b+build.1.1b",
      (1, 2, "3b", 4), "pre.1.2b", "build.1.1b"),
     ("0.2.3+b178",
      (0, 2, 3, None), None, "b178")
     ]


@pytest.mark.parametrize("v_str, main, build, pre", v)
def test_parse(v_str, main, build, pre):
    v1 = Version(v_str)
    assert v1.major == main[0]
    assert v1.minor == main[1]
    assert v1.patch == main[2]
    assert v1.micro == main[3]
    assert v1.pre == build
    assert v1.build == pre
