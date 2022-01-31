import textwrap

from conans.test.utils.tools import TestClient


def test_bazel():
    # https://github.com/conan-io/conan/issues/10471
    dep = textwrap.dedent("""
        from conan import ConanFile
        class ExampleConanIntegration(ConanFile):
            name = "dep"
            version = "0.1"
            def package_info(self):
                self.cpp_info.includedirs = []
                self.cpp_info.libs = []
        """)
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.google import BazelToolchain, BazelDeps

        class ExampleConanIntegration(ConanFile):
            generators = 'BazelDeps', 'BazelToolchain'
            requires = 'dep/0.1',
        """)
    c = TestClient()
    c.save({"dep/conanfile.py": dep,
            "consumer/conanfile.py": conanfile})
    c.run("create dep")
    c.run("install consumer")
    assert "conanfile.py: Generator 'BazelToolchain' calling 'generate()'" in c.out
