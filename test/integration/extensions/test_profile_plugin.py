import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


@pytest.mark.parametrize("compiler, version, cppstd, correct", [
    ("gcc", "4.1", "11", False),
    ("gcc", "4.4", "11", True),
    ("gcc", "4.4", "14", False),
    ("gcc", "4.4", "17", False),
    ("gcc", "4.4", "20", False),
    ("gcc", "4.8", "11", True),
    ("gcc", "4.8", "14", True),
    ("gcc", "4.8", "17", False),
    ("gcc", "4.8", "20", False),
    ("gcc", "5", "17", True),
    ("gcc", "5", "20", False),
    ("gcc", "8", "17", True),
    ("gcc", "8", "20", True),
    ("clang", "3.3", "11", True),
    ("clang", "3.3", "14", False),
    ("clang", "3.4", "14", True),
    ("clang", "3.4", "17", False),
    ("clang", "3.5", "17", True),
    ("clang", "3.5", "20", False),
    ("clang", "5.0", "20", False),
    ("clang", "6.0", "20", True),
    ("apple-clang", "5.0", "98", True),
    ("apple-clang", "5.0", "11", True),
    ("apple-clang", "5.1", "14", True),
    ("apple-clang", "5.1", "17", False),
    ("apple-clang", "6.1", "17", True),
    ("apple-clang", "6.1", "20", False),
    ("apple-clang", "10.0", "20", True),
    ("msvc", "170", "14", False),
    ("msvc", "190", "14", True),
    ("msvc", "190", "20", False),
    ("msvc", "191", "14", True),
    ("msvc", "191", "17", True),
    ("msvc", "191", "20", False),
    ("msvc", "193", "20", True)
])
def test_invalid_cppstd(compiler, version, cppstd, correct):
    c = TestClient()
    c.save({"conanfile.py": GenConanfile()})
    c.run("install . -s compiler={} -s compiler.version={} "
          "-s compiler.cppstd={}".format(compiler, version, cppstd), assert_error=not correct)
    if not correct:
        assert "ConanException: The provided compiler.cppstd" in c.out
