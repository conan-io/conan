from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def test_test_requires():
    c = TestClient()
    c.save({"test/conanfile.py": GenConanfile("test", "0.1"),
            "consumer/conanfile.txt": "[test_requires]\ntest/0.1"})
    c.run("create test")
    c.run("install consumer")
    c.assert_listed_require({"test/0.1": "Cache"}, test=True)
    c.assert_listed_binary({"test/0.1": ("da39a3ee5e6b4b0d3255bfef95601890afd80709", "Cache")},
                           test=True)


def test_test_requires_options():
    c = TestClient()
    c.save({"test/conanfile.py": GenConanfile("test", "0.1").with_option("myoption", [1, 2, 3]),
            "consumer/conanfile.txt": "[test_requires]\ntest/0.1\n[options]\n*:myoption=2"})
    c.run("create test -o myoption=2")
    c.assert_listed_binary({"test/0.1": ("a3cb1345b8297bfdffea4ef4bb1b2694c54d1d69", "Build")})

    c.run("install consumer")
    c.assert_listed_require({"test/0.1": "Cache"}, test=True)
    c.assert_listed_binary({"test/0.1": ("a3cb1345b8297bfdffea4ef4bb1b2694c54d1d69", "Cache")},
                           test=True)
