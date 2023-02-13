import textwrap

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


class TestTestRequiresDiamond:
    def test_test_requires_linear(self):
        c = TestClient()
        c.save({"zlib/conanfile.py": GenConanfile("zlib", "1.0"),
                "gtest/conanfile.py": GenConanfile("gtest", "1.0").with_requires("zlib/1.0"),
                "engine/conanfile.py": GenConanfile("engine", "1.0").with_test_requires("gtest/1.0")
                })
        c.run("create zlib")
        c.run("create gtest")
        c.run("install engine")
        c.assert_listed_require({"gtest/1.0": "Cache",
                                 "zlib/1.0": "Cache"}, test=True)

    def test_test_requires_half_diamond(self):
        c = TestClient()
        c.save({"zlib/conanfile.py": GenConanfile("zlib", "1.0"),
                "gtest/conanfile.py": GenConanfile("gtest", "1.0").with_requires("zlib/1.0"),
                "engine/conanfile.py": GenConanfile("engine", "1.0").with_requires("zlib/1.0")
                                                                    .with_test_requires("gtest/1.0")
                })
        c.run("create zlib")
        c.run("create gtest")
        c.run("install engine")
        c.assert_listed_require({"zlib/1.0": "Cache"})
        c.assert_listed_require({"gtest/1.0": "Cache"}, test=True)

    def test_test_requires_half_diamond_change_order(self):
        engine = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                def requirements(self):
                    self.test_requires("gtest/1.0")
                    self.requires("zlib/1.0")
            """)
        c = TestClient()
        c.save({"zlib/conanfile.py": GenConanfile("zlib", "1.0"),
                "gtest/conanfile.py": GenConanfile("gtest", "1.0").with_requires("zlib/1.0"),
                "engine/conanfile.py": engine
                })
        c.run("create zlib")
        c.run("create gtest")
        c.run("install engine")
        c.assert_listed_require({"zlib/1.0": "Cache"})
        c.assert_listed_require({"gtest/1.0": "Cache"}, test=True)

    def test_test_requires_diamond(self):
        c = TestClient()
        c.save({"zlib/conanfile.py": GenConanfile("zlib", "1.0"),
                "gtest/conanfile.py": GenConanfile("gtest", "1.0").with_requires("zlib/1.0"),
                "engine/conanfile.py": GenConanfile("engine", "1.0").with_requires("zlib/1.0"),
                "game/conanfile.py": GenConanfile().with_requires("engine/1.0")
                                                   .with_test_requires("gtest/1.0")
                })
        c.run("create zlib")
        c.run("create gtest")
        c.run("create engine")
        c.run("install game")
        c.assert_listed_require({"zlib/1.0": "Cache",
                                 "engine/1.0": "Cache"})
        c.assert_listed_require({"gtest/1.0": "Cache"}, test=True)

    def test_test_requires_diamond_change_order(self):
        c = TestClient()
        game = textwrap.dedent("""
           from conan import ConanFile
           class Pkg(ConanFile):
               def requirements(self):
                   self.test_requires("gtest/1.0")
                   self.requires("engine/1.0")
           """)
        c.save({"zlib/conanfile.py": GenConanfile("zlib", "1.0"),
                "gtest/conanfile.py": GenConanfile("gtest", "1.0").with_requires("zlib/1.0"),
                "engine/conanfile.py": GenConanfile("engine", "1.0").with_requires("zlib/1.0"),
                "game/conanfile.py": game
                })
        c.run("create zlib")
        c.run("create gtest")
        c.run("create engine")
        c.run("install game")
        c.assert_listed_require({"zlib/1.0": "Cache",
                                 "engine/1.0": "Cache"})
        c.assert_listed_require({"gtest/1.0": "Cache"}, test=True)
