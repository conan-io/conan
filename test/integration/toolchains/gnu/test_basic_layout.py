import os
import platform
import textwrap
import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient

@pytest.mark.parametrize("basic_layout, expected_path", [
    ('basic_layout(self)', 'build-release'),
    ('basic_layout(self, build_folder="custom_build_folder")', 'custom_build_folder')])
def test_basic_layout_subproject(basic_layout, expected_path):
    c = TestClient()
    conanfile = textwrap.dedent(f"""
        from conan import ConanFile
        from conan.tools.layout import basic_layout
        class Pkg(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            generators = "AutotoolsToolchain"
            def layout(self):
                self.folders.root = ".."
                self.folders.subproject = "pkg"
                {basic_layout}
        """)
    c.save({"pkg/conanfile.py": conanfile})
    c.run("install pkg")
    ext = "sh" if platform.system() != "Windows" else "bat"
    assert os.path.isfile(os.path.join(c.current_folder, "pkg", expected_path, "conan",
                                       "conanautotoolstoolchain.{}".format(ext)))


def test_editable_includes():
    c = TestClient()
    dep = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.layout import basic_layout

        class Dep(ConanFile):
            name = "dep"
            version = "0.1"
            def layout(self):
                basic_layout(self, src_folder="src")
            """)
    c.save({"dep/conanfile.py": dep,
            "pkg/conanfile.py": GenConanfile("pkg", "0.1").with_settings("build_type", "arch")
                                                          .with_requires("dep/0.1")})
    c.run("editable add dep")
    c.run("install pkg -s arch=x86_64 -g CMakeDeps -g PkgConfigDeps -g XcodeDeps")
    data = c.load(f"pkg/dep-release-x86_64-data.cmake")
    assert 'set(dep_INCLUDE_DIRS_RELEASE "${dep_PACKAGE_FOLDER_RELEASE}/src/include")' in data
    pc = c.load("pkg/dep.pc")
    assert "includedir=${prefix}/src/include" in pc
    xcode = c.load("pkg/conan_dep_dep_release_x86_64.xcconfig")
    dep_path = os.path.join(c.current_folder, "dep", "src", "include")
    assert f"SYSTEM_HEADER_SEARCH_PATHS_dep_dep[config=Release][arch=x86_64][sdk=*] = \"{dep_path}\"" in xcode


def test_editable_includes_previously_defined():
    # if someone already defined self.cpp.source.includedirs make sure we don't overwrite
    # their value
    c = TestClient()
    dep = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.layout import basic_layout

        class Dep(ConanFile):
            name = "dep"
            version = "0.1"
            def layout(self):
                self.cpp.source.includedirs = ["somefolder"]
                basic_layout(self, src_folder="src")
            """)
    c.save({"dep/conanfile.py": dep,
            "pkg/conanfile.py": GenConanfile("pkg", "0.1").with_settings("build_type", "arch")
                                                          .with_requires("dep/0.1")})
    c.run("editable add dep")
    c.run("install pkg -s arch=x86_64 -g CMakeDeps -g PkgConfigDeps -g XcodeDeps")
    data = c.load(f"pkg/dep-release-x86_64-data.cmake")
    assert 'set(dep_INCLUDE_DIRS_RELEASE "${dep_PACKAGE_FOLDER_RELEASE}/src/somefolder")' in data
    pc = c.load("pkg/dep.pc")
    assert "includedir=${prefix}/src/somefolder" in pc
    xcode = c.load("pkg/conan_dep_dep_release_x86_64.xcconfig")
    dep_path = os.path.join(c.current_folder, "dep", "src", "somefolder")
    assert f"SYSTEM_HEADER_SEARCH_PATHS_dep_dep[config=Release][arch=x86_64][sdk=*] = \"{dep_path}\"" in xcode
