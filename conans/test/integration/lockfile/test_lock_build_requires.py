import json

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_lock_build_tool_requires():
    c = TestClient()
    c.save({"common/conanfile.py": GenConanfile("common", "1.0").with_settings("os"),
            "tool/conanfile.py": GenConanfile("tool", "1.0").with_settings("os")
                                                            .with_requires("common/1.0"),
            "lib/conanfile.py": GenConanfile("lib", "1.0").with_settings("os")
                                                          .with_requires("tool/1.0"),
            "consumer/conanfile.py":
                GenConanfile("consumer", "1.0").with_settings("os")
                                               .with_requires("lib/1.0")
                                               .with_build_requires("tool/1.0")})
    c.run("export common")
    c.run("export tool")
    c.run("export lib")
    # cross compile Linux->Windows
    c.run("lock create consumer/conanfile.py -s:h os=Linux -s:b os=Windows --build=*")
    c.run("install --tool-requires=tool/1.0 --build=missing --lockfile=consumer/conan.lock "
          "-s:h os=Linux -s:b os=Windows")
    c.assert_listed_binary({"tool/1.0": ("78ba71aef65089d6e3244756171f9f37d5a76223", "Build"),
                            "common/1.0": ("ebec3dc6d7f6b907b3ada0c3d3cdc83613a2b715", "Build")},
                           build=True)


def test_lock_buildrequires_create():
    c = TestClient()
    c.save({"conanfile.py": GenConanfile("tool", "0.1")})
    c.run("create .  --build-require --lockfile-out=conan.lock")
    lock = json.loads(c.load("conan.lock"))
    assert "tool/0.1#2d65f1b4af1ce59028f96adbfe7ed5a2" in lock["build_requires"][0]


def test_lock_buildrequires_export():
    c = TestClient()
    c.save({"conanfile.py": GenConanfile("tool", "0.1")})
    c.run("export . --build-require --lockfile-out=conan.lock")
    lock = json.loads(c.load("conan.lock"))
    assert "tool/0.1#2d65f1b4af1ce59028f96adbfe7ed5a2" in lock["build_requires"][0]


def test_lock_buildrequires_create_transitive():
    c = TestClient()
    c.save({"dep/conanfile.py": GenConanfile("dep", "0.1"),
            "tool/conanfile.py": GenConanfile("tool", "0.1").with_requires("dep/0.1")})
    c.run("create dep")
    c.run("create tool --build-require --lockfile-out=conan.lock")
    lock = json.loads(c.load("conan.lock"))
    assert "tool/0.1#e4f0da4d9097c4da0725ea25b8bf83c8" in lock["build_requires"][0]
    assert "dep/0.1#f8c2264d0b32a4c33f251fe2944bb642" in lock["build_requires"][1]
