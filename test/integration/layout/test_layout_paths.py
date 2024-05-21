import os
import textwrap

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def test_editable_layout_paths():
    # https://github.com/conan-io/conan/issues/12521
    # https://github.com/conan-io/conan/issues/12839
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
                                                          .with_generator("PkgConfigDeps")
                                                          .with_generator("XcodeDeps")})
    c.run("editable add dep")
    c.run("install pkg -s arch=x86_64")
    # It doesn't crash anymore

    assert "dep/0.1:da39a3ee5e6b4b0d3255bfef95601890afd80709 - Editable" in c.out
    data = c.load(f"pkg/dep-release-x86_64-data.cmake")

    assert 'set(dep_INCLUDE_DIRS_RELEASE "${dep_PACKAGE_FOLDER_RELEASE}/include")' in data
    pc = c.load("pkg/dep.pc")
    assert "includedir=${prefix}/include" in pc
    xcode = c.load("pkg/conan_dep_dep_release_x86_64.xcconfig")
    dep_path = os.path.join(c.current_folder, "dep")
    assert f"PACKAGE_ROOT_dep[config=Release][arch=x86_64][sdk=*] = {dep_path}" in xcode


def test_layout_paths_normalized():
    # make sure the paths doesn't end with trailing ".", and they are identical to the cwd
    c = TestClient()
    dep = textwrap.dedent("""
        import os
        from conan import ConanFile

        class Dep(ConanFile):
            name = "dep"
            version = "0.1"
            def layout(self):
                self.folders.source = "."
                self.folders.build = "."
                self.folders.generators = "."

            def build(self):
                assert os.getcwd() == self.source_folder
                assert os.getcwd() == self.build_folder
                assert os.getcwd() == self.generators_folder

            """)
    c.save({"conanfile.py": dep})
    c.run("build .")
    # It doesn't assert in the build()
