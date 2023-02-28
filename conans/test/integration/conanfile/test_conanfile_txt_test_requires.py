from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_test_requires():
    c = TestClient()
    c.save({"test/conanfile.py": GenConanfile("test", "0.1"),
            "consumer/conanfile.txt": "[test_requires]\ntest/0.1"})
    c.run("create test")
    c.run("install consumer")
    c.assert_listed_require({"test/0.1": "Cache"}, test=True)
    c.assert_listed_binary({"test/0.1": ("da39a3ee5e6b4b0d3255bfef95601890afd80709", "Cache")},
                           test=True)
