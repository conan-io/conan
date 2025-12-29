import re
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


def test_skip():
    # https://github.com/conan-io/conan/issues/13439
    c = TestClient()
    global_conf = textwrap.dedent("""
        tools.graph:skip_test=True
        tools.build:skip_test=True
        """)
    c.save_home({"global.conf": global_conf})
    c.save({"pkga/conanfile.py": GenConanfile("pkga", "1.0.0"),
            "pkgb/conanfile.py": GenConanfile("pkgb", "1.0.0").with_test_requires("pkga/1.0.0"),
            "pkgc/conanfile.py": GenConanfile("pkgc", "1.0.0").with_test_requires("pkgb/1.0.0")})
    c.run("create pkga")
    c.run("create pkgb")

    # Always skipped
    c.run("install pkgc")
    # correct, pkga and pkgb are not in the output at all, they have been skipped
    assert "pkga" not in c.out
    assert "pkgb" not in c.out

    # not skipping test-requires
    c.run("install pkgc -c tools.graph:skip_test=False")
    # correct, pkga and pkgb are not skipped now
    assert "pkga" in c.out
    assert "pkgb" in c.out
    # but pkga binary is not really necessary
    assert re.search(r"Skipped binaries(\s*)pkga/1.0.0", c.out)

    # skipping all but the current one
    c.run("install pkgc -c &:tools.graph:skip_test=False")
    # correct, only pkga  is skipped now
    assert "pkga" not in c.out
    assert "pkgb" in c.out
