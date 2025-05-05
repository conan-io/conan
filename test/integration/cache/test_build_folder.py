import os.path
import textwrap

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def test_folder_removed():
    tc = TestClient(light=True)
    conanfile = textwrap.dedent("""
    import os
    import time
    from conan import ConanFile
    from conan.tools.cmake import cmake_layout
    from conan.tools.files import copy, rmdir

    class Pkg(ConanFile):
        name = "pkg"
        version = "0.1"

        def build(self):
            with open(os.path.join(self.build_folder, "file.txt"), "w") as f:
                f.write(str(time.time()))

        def package(self):
            copy(self, "file.txt", dst=self.package_folder, src=self.build_folder)
    """)
    tc.save({"conanfile.py": conanfile})

    tc.run("create .")
    first_create_layout = tc.created_layout()
    assert os.path.exists(first_create_layout.build())

    tc.run("create .")
    second_create_layout = tc.created_layout()
    assert os.path.exists(second_create_layout.build())

    assert first_create_layout.build() != second_create_layout.build()
    assert first_create_layout.package() != second_create_layout.package()
