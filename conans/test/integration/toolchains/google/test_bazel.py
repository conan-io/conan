import textwrap

from conans.test.assets.genconanfile import GenConanfile
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


def test_bazel_relative_paths():
    # https://github.com/conan-io/conan/issues/10476
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.google import BazelToolchain, BazelDeps

        class ExampleConanIntegration(ConanFile):
            generators = 'BazelDeps', 'BazelToolchain'
            requires = 'dep/0.1'

            def layout(self):
                self.folders.generators = "conandeps"
        """)
    c = TestClient()
    c.save({"dep/conanfile.py": GenConanfile("dep", "0.1"),
            "consumer/conanfile.py": conanfile})
    c.run("create dep")
    c.run("install consumer")
    assert "conanfile.py: Generator 'BazelToolchain' calling 'generate()'" in c.out
    build_file = c.load("consumer/conandeps/dep/BUILD")
    assert 'hdrs = glob(["include/**"])' in build_file
    assert 'includes = ["include"]' in build_file


def test_bazel_exclude_folders():
    # https://github.com/conan-io/conan/issues/11081
    dep = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import save
        class ExampleConanIntegration(ConanFile):
            name = "dep"
            version = "0.1"
            def package(self):
                save(self, os.path.join(self.package_folder, "lib", "mymath", "otherfile.a"), "")
                save(self, os.path.join(self.package_folder, "lib", "libmymath.a"), "")
            def package_info(self):
                self.cpp_info.libs = ["mymath"]
        """)
    c = TestClient()
    c.save({"dep/conanfile.py": dep})
    c.run("create dep")
    c.run("install dep/0.1@ -g BazelDeps")
    build_file = c.load("dep/BUILD")
    assert 'static_library = "lib/libmymath.a"' in build_file
