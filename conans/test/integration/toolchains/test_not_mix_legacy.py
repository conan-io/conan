import textwrap

from conans.test.utils.tools import TestClient


def test_not_mix_legacy_cmake():
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conans import CMake
        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"
            settings = "build_type"
            generators = "CMakeDeps"
            def build(self):
                CMake(self)
            """)
    c.save({"conanfile.py": conanfile})
    c.run("create .", assert_error=True)
    assert "Using the wrong 'CMake' helper" in c.out


def test_not_mix_legacy_cmake_generate():
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conans import CMake
        from conan.tools.cmake import CMakeDeps
        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"
            settings = "build_type"
            def generate(self):
                CMakeDeps(self)
            def build(self):
                CMake(self)
            """)
    c.save({"conanfile.py": conanfile})
    c.run("create .", assert_error=True)
    assert "Using the wrong 'CMake' helper" in c.out


def test_not_mix_legacy_msbuild():
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conans import MSBuild
        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"
            settings = "build_type", "arch"
            generators = "MSBuildDeps"
            def build(self):
                MSBuild(self)
            """)
    c.save({"conanfile.py": conanfile})
    c.run("create .", assert_error=True)
    assert "Using the wrong 'MSBuild' helper" in c.out


def test_not_mix_legacy_msbuild_generate():
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conans import MSBuild
        from conan.tools.microsoft import MSBuildDeps
        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"
            settings = "build_type", "arch"
            def generate(self):
                MSBuildDeps(self)
            def build(self):
                MSBuild(self)
            """)
    c.save({"conanfile.py": conanfile})
    c.run("create .", assert_error=True)
    assert "Using the wrong 'MSBuild' helper" in c.out
