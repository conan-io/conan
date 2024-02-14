import re
import textwrap

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_repackage():
    # consumer -> repackager -> liba
    #                  \------> libb
    client = TestClient()
    client.save({"conanfile.py": GenConanfile().with_package_file("liba.txt", "HelloA!")})
    client.run("create . --name=liba --version=1.0")
    client.save({"conanfile.py": GenConanfile().with_package_file("libb.txt", "HelloB!")})
    client.run("create . --name=libb --version=1.0 ")

    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import copy
        class Pkg(ConanFile):
            settings = "os"

            def requirements(self):
                self.requires("liba/1.0", headers=True, libs=True, visible=False, run=False)
                self.requires("libb/1.0", headers=True, libs=True, visible=False, run=False)

            def package(self):
                for r, d in self.dependencies.items():
                    copy(self, "*", src=d.package_folder,
                         dst=os.path.join(self.package_folder, r.ref.name))
        """)
    client.save({"conanfile.py": conanfile})
    client.run("create . --name=repackager --version=1.0")

    client.save({"conanfile.py": GenConanfile().with_requires("repackager/1.0")}, clean_first=True)
    client.run("install .")
    assert re.search(r"Skipped binaries(\s*)liba/1.0, libb/1.0", client.out)
    assert "repackager/1.0: Already installed!" in client.out
