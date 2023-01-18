import os
import textwrap

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


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
    c.run("editable add dep dep/0.1")
    c.run("install pkg -s arch=x86_64")
    # It doesn't crash anymore
    assert "dep/0.1:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Editable" in c.out
    data = c.load(f"dep-release-x86_64-data.cmake")
    assert 'set(dep_INCLUDE_DIRS_RELEASE "${dep_PACKAGE_FOLDER_RELEASE}/include")' in data
    pc = c.load("dep.pc")
    assert "includedir1=${prefix}/include" in pc
    xcode = c.load("conan_dep_dep_release_x86_64.xcconfig")
    dep_path = os.path.join(c.current_folder, "dep")
    assert f"PACKAGE_ROOT_dep[config=Release][arch=x86_64][sdk=*] = {dep_path}" in xcode
