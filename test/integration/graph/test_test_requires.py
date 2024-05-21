import textwrap

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


class TestTestRequiresDiamond:
    def test_test_requires_linear(self):
        c = TestClient(light=True)
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
        c = TestClient(light=True)
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
        c = TestClient(light=True)
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
        c = TestClient(light=True)
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
        c = TestClient(light=True)
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

    def test_test_requires_conflict_force(self):
        c = TestClient(light=True)
        game = textwrap.dedent("""
           from conan import ConanFile
           class Pkg(ConanFile):
               def requirements(self):
                   self.test_requires("gtest/1.0", force=True)
                   self.test_requires("rapidcheck/1.0")
           """)
        c.save({"gtest/conanfile.py": GenConanfile("gtest"),
                "rapidcheck/conanfile.py":
                    GenConanfile("rapidcheck", "1.0").with_requires("gtest/1.1"),
                "game/conanfile.py": game
                })
        c.run("create gtest --version=1.0")
        c.run("create gtest --version=1.1")
        c.run("create rapidcheck")
        c.run("install game")
        c.assert_listed_require({"gtest/1.0": "Cache"}, test=True)
        c.assert_overrides({"gtest/1.1": ["gtest/1.0"]})


def test_require_options():
    c = TestClient(light=True)
    gtest = textwrap.dedent("""
        from conan import ConanFile
        class Gtest(ConanFile):
            name = "gtest"
            version = "1.0"
            options = {"myoption": [1, 2, 3]}
            default_options = {"myoption": 1}
            def package_info(self):
                self.output.info(f"MYOPTION: {self.options.myoption}")
        """)
    engine = textwrap.dedent("""
        from conan import ConanFile
        class Engine(ConanFile):
            name = "engine"
            version = "1.0"
            def build_requirements(self):
                self.test_requires("gtest/1.0", options={"myoption": "2"})
        """)
    c.save({"gtest/conanfile.py": gtest,
            "engine/conanfile.py": engine})
    c.run("create gtest")
    c.run("create gtest -o gtest*:myoption=2")
    c.run("create gtest -o gtest*:myoption=3")
    c.run("create engine")
    assert "gtest/1.0: MYOPTION: 2" in c.out
    c.run("create engine -o gtest*:myoption=3")
    assert "gtest/1.0: MYOPTION: 3" in c.out


def test_requires_components():
    """ this test used to fail with "gtest" not required by components
    It is important to have at least 1 external ``requires`` because with
    no requires at all it doesn't fail.
    https://github.com/conan-io/conan/issues/13187
    """
    c = TestClient(light=True)
    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class MyLib(ConanFile):
            name = "mylib"
            version = "0.1"

            requires = "openssl/1.1"
            test_requires = "gtest/1.0"

            def package_info(self):
                self.cpp_info.components["mylib"].requires = ["openssl::openssl"]
        """)
    c.save({"gtest/conanfile.py": GenConanfile("gtest", "1.0"),
            "openssl/conanfile.py": GenConanfile("openssl", "1.1"),
            "pkg/conanfile.py": conanfile})
    c.run("create gtest")
    c.run("create openssl")
    c.run("create pkg")
    # This NO LONGER FAILS
    c.assert_listed_require({"gtest/1.0": "Cache"}, test=True)


def test_requires_transitive_diamond_components():
    """
    libc -----> libb ----> liba
     |-(test-requires)----/
    https://github.com/conan-io/conan/issues/13892
    """
    c = TestClient(light=True)
    libc = textwrap.dedent("""
        from conan import ConanFile
        class LibC(ConanFile):
            name = "libc"
            version = "0.1"
            requires = "libb/1.0"
            test_requires = "liba/1.0"
            def package_info(self):
                 self.cpp_info.components["comp"].libs = ["libc"]
                 self.cpp_info.components["comp"].requires.append("libb::libb")
        """)
    c.save({"liba/conanfile.py": GenConanfile("liba", "1.0"),
            "libb/conanfile.py": GenConanfile("libb", "1.0").with_requires("liba/1.0"),
            "libc/conanfile.py": libc})
    c.run("create liba")
    c.run("create libb")
    c.run("create libc")
    # This used to crash due to component not defined to liba
    assert "libc/0.1: Created package" in c.out


def test_test_requires_options():
    """ the default_options = {} values also propagate to ``test_requires()`` """
    c = TestClient(light=True)
    c.save({"test/conanfile.py": GenConanfile("test", "0.1").with_option("myoption", [1, 2, 3]),
            "consumer/conanfile.py": GenConanfile().with_test_requires("test/0.1")
                                                   .with_default_option("test/*:myoption", "2")})
    c.run("create test -o myoption=2")
    c.assert_listed_binary({"test/0.1": ("a3cb1345b8297bfdffea4ef4bb1b2694c54d1d69", "Build")})

    c.run("install consumer")
    c.assert_listed_require({"test/0.1": "Cache"}, test=True)
    c.assert_listed_binary({"test/0.1": ("a3cb1345b8297bfdffea4ef4bb1b2694c54d1d69", "Cache")},
                           test=True)


def test_invisible_requires_options():
    """ the default_options = {} values also propagate to ``requires(visible=False)`` """
    c = TestClient(light=True)
    c.save({"test/conanfile.py": GenConanfile("test", "0.1").with_option("myoption", [1, 2, 3]),
            "consumer/conanfile.py": GenConanfile().with_requirement("test/0.1", visible=False)
                                                   .with_default_option("test/*:myoption", "2")})
    c.run("create test -o myoption=2")
    c.assert_listed_binary({"test/0.1": ("a3cb1345b8297bfdffea4ef4bb1b2694c54d1d69", "Build")})

    c.run("install consumer")
    c.assert_listed_require({"test/0.1": "Cache"})
    c.assert_listed_binary({"test/0.1": ("a3cb1345b8297bfdffea4ef4bb1b2694c54d1d69", "Cache")})
