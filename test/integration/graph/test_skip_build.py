import textwrap

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def test_graph_skip_build_test():
    # app -> pkg -(test)-> gtest
    #         \---(tool)-> cmake
    c = TestClient(light=True)
    pkg = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            name = "pkg"
            version = "1.0"
            test_requires = "gtest/1.0"
            tool_requires = "cmake/1.0"
        """)
    c.save({"gtest/conanfile.py": GenConanfile("gtest", "1.0"),
            "cmake/conanfile.py": GenConanfile("cmake", "1.0"),
            "pkg/conanfile.py": pkg,
            "app/conanfile.py": GenConanfile("app", "1.0").with_requires("pkg/1.0")})
    c.run("create gtest")
    c.run("create cmake")
    c.run("create pkg")
    c.run("create app -c tools.graph:skip_build=True -c tools.graph:skip_test=True")
    assert "cmake" not in c.out
    assert "gtest" not in c.out
    c.run("create app -c tools.graph:skip_test=True")
    assert "WARN: experimental: Usage of 'tools.graph:skip_test'" in c.out
    assert "WARN: tools.graph:skip_test set, but tools.build:skip_test is not" in c.out
    assert "cmake" in c.out
    assert "gtest" not in c.out
    c.run("create app -c tools.graph:skip_build=True")
    assert "cmake" not in c.out
    assert "gtest" in c.out

    c.run("install app")
    assert "cmake" in c.out
    assert "gtest" in c.out

    c.run("install app -c tools.graph:skip_build=True -c tools.graph:skip_test=True")
    assert "cmake" not in c.out
    assert "gtest" not in c.out

    c.run("install app -c tools.graph:skip_build=True --build=pkg/*", assert_error=True)
    assert "ERROR: Package pkg/1.0 skipped its test/tool requires with tools.graph:skip_build, " \
           "but was marked to be built " in c.out
