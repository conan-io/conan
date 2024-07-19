import os
import textwrap

from conan.test.utils.tools import TestClient


def test_no_copy_source():
    conanfile = textwrap.dedent('''
        from conan import ConanFile
        from conan.tools.files import copy, save, load
        import os

        class ConanFileToolsTest(ConanFile):
            name = "pkg"
            version = "0.1"
            exports_sources = "*"
            no_copy_source = True

            def source(self):
                save(self, "header.h", "artifact contents!")

            def build(self):
                self.output.info("Source files: %s" % load(self,
                                          os.path.join(self.source_folder, "file.h")))
                save(self, "myartifact.lib", "artifact contents!")

            def package(self):
                copy(self, "*", self.source_folder, self.package_folder)
                copy(self, "*", self.build_folder, self.package_folder)
        ''')

    client = TestClient()
    client.save({"conanfile.py": conanfile,
                 "file.h": "myfile.h contents"})
    client.run("create .")
    assert "Source files: myfile.h contents" in client.out
    layout = client.created_layout()
    build_folder = layout.build()
    package_folder = layout.package()

    assert "file.h" not in os.listdir(build_folder)
    assert "header.h" not in os.listdir(build_folder)
    assert "file.h" in os.listdir(package_folder)
    assert "header.h" in os.listdir(package_folder)
    assert "myartifact.lib" in os.listdir(package_folder)
