import textwrap

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def test_components_test_requires():
    # https://github.com/conan-io/conan/issues/17164
    c = TestClient(light=True)
    pkg = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            name = "pkg"
            version = "1.0"

            def requirements(self):
                self.requires("json/1.0")

            def build_requirements(self):
                self.test_requires("gtest/1.0")

            def package_info(self):
                self.cpp_info.requires = ['json::mycomp']
        """)
    c.save({"gtest/conanfile.py": GenConanfile("gtest", "1.0"),
            "json/conanfile.py": GenConanfile("json", "1.0"),
            "pkg/conanfile.py": pkg,
            "pkg/test_package/conanfile.py": GenConanfile().with_test("pass")})

    c.run("create gtest")
    c.run("create json")
    c.run("create pkg")
    print(c.out)
