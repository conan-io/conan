import textwrap

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_editable_layout_paths():
    # https://github.com/conan-io/conan/issues/12521
    c = TestClient()
    dep = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import save
        class Dep(ConanFile):
            name = "dep"
            version = "0.1"
            def layout(self):
                self.cpp.source.includedirs = ["include"]
            """)
    c.save({"dep/conanfile.py": dep,
            "pkg/conanfile.py": GenConanfile("pkg", "0.1").with_settings("build_type", "arch")
                                                          .with_requires("dep/0.1")
                                                          .with_generator("CMakeDeps")
                                                          .with_generator("PkgConfigDeps")})
    c.run("editable add dep dep/0.1")
    c.run("install pkg")
    # It doesn't crash anymore
    assert "dep/0.1:da39a3ee5e6b4b0d3255bfef95601890afd80709 - Editable" in c.out
    arch = c.get_default_host_profile().settings['arch']
    data = c.load(f"pkg/dep-release-{arch}-data.cmake")
    assert 'set(dep_INCLUDE_DIRS_RELEASE "${dep_PACKAGE_FOLDER_RELEASE}/include")' in data
    pc = c.load("pkg/dep.pc")
    assert "includedir1=${prefix}/include" in pc
