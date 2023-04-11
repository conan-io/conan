import json
import textwrap

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


def test_lock_create_build_require_transitive():
    """ cross compiling from Windows to Linux
    """
    c = TestClient()
    dep = textwrap.dedent("""
        from conan import ConanFile
        class Dep(ConanFile):
            name = "dep"
            settings = "os"
            def package_id(self):
                self.output.info(f"MYOS:{self.info.settings.os}!!")
                self.output.info(f"TARGET:{self.settings_target.os}!!")
            """)
    tool = textwrap.dedent("""
        from conan import ConanFile
        class Tool(ConanFile):
           name = "tool"
           version = "0.1"
           requires = "dep/[*]"
           settings = "os"
           def generate(self):
               self.output.info(f"MYOS-GEN:{self.info.settings.os}!!")
               self.output.info(f"TARGET-GEN:{self.settings_target.os}!!")
           def package_id(self):
               self.output.info(f"MYOS:{self.info.settings.os}!!")
               self.output.info(f"TARGET:{self.settings_target.os}!!")
           """)
    c.save({"dep/conanfile.py": dep,
            "tool/conanfile.py": tool})
    c.run("create dep --build-require --version=0.1 -s:b os=Windows -s:h os=Linux")
    assert "dep/0.1: MYOS:Windows!!" in c.out
    assert "dep/0.1: TARGET:Linux!!" in c.out

    # The lockfile should contain dep in build-requires
    c.run("lock create tool --build-require -s:b os=Windows -s:h os=Linux")
    assert "dep/0.1: MYOS:Windows!!" in c.out
    assert "dep/0.1: TARGET:Linux!!" in c.out
    lock = json.loads(c.load("tool/conan.lock"))
    assert "dep/0.1" in lock["build_requires"][0]

    # Now try to apply it in  graph info, even if a new 0.2 verion si there
    c.run("create dep --build-require --version=0.2 -s:b os=Windows -s:h os=Linux")
    assert "dep/0.2: MYOS:Windows!!" in c.out
    assert "dep/0.2: TARGET:Linux!!" in c.out

    c.run("graph info tool --build-require -s:b os=Windows -s:h os=Linux")
    c.assert_listed_require({"dep/0.1": "Cache"}, build=True)
    assert "dep/0.1: MYOS:Windows!!" in c.out
    assert "dep/0.1: TARGET:Linux!!" in c.out
    assert "conanfile.py (tool/0.1): MYOS:Windows!!" in c.out
    assert "conanfile.py (tool/0.1): TARGET:Linux!!" in c.out
    assert "context: build" in c.out
    assert "context: host" not in c.out

    c.run("install tool --build-require -s:b os=Windows -s:h os=Linux")
    c.assert_listed_require({"dep/0.1": "Cache"}, build=True)
    assert "dep/0.1: MYOS:Windows!!" in c.out
    assert "dep/0.1: TARGET:Linux!!" in c.out
    assert "conanfile.py (tool/0.1): MYOS:Windows!!" in c.out
    assert "conanfile.py (tool/0.1): TARGET:Linux!!" in c.out
    assert "conanfile.py (tool/0.1): MYOS-GEN:Windows!!" in c.out
    assert "conanfile.py (tool/0.1): TARGET-GEN:Linux!!" in c.out
