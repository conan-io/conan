import re
import textwrap

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def test_repackage():
    # consumer -> repackager -> liba
    #                  \------> libb
    client = TestClient(light=True)
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


def test_repackage_library_self():
    c = TestClient()
    c.save({"conanfile.py": GenConanfile("liba", "1.0").with_package_file("a.txt", "A1.0!")})
    c.run("create .")

    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import copy
        class Pkg(ConanFile):
            name = "liba"
            version = "2.0"

            def requirements(self):
                self.requires("liba/1.0", visible=False)

            def package(self):
                for _, dep in self.dependencies.items():
                    copy(self, "*", src=dep.package_folder, dst=self.package_folder)
        """)
    c.save({"conanfile.py": conanfile})
    c.run("create .")

    c.run("install --requires=liba/2.0 --deployer=full_deploy")
    assert re.search(r"Skipped binaries(\s*)liba/1.0", c.out)
    assert "liba/2.0: Already installed!" in c.out
    assert c.load("full_deploy/host/liba/2.0/a.txt") == "A1.0!"


def test_repackage_library_self_infinite_loop():
    c = TestClient()

    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            name = "liba"
            version = "1.0"

            def requirements(self):
                self.requires("liba/1.0", visible=False, headers=False, libs=False, run=False)
        """)
    c.save({"conanfile.py": conanfile})
    c.run("create .", assert_error=True)
    assert "There is a cycle/loop in the graph" in c.out


def test_repackage_library_self_multiple():
    c = TestClient()
    c.save({"1/conanfile.py": GenConanfile("liba", "1.0").with_package_file("a1.txt", "A1.0!"),
            "2/conanfile.py": GenConanfile("liba", "2.0").with_package_file("a2.txt", "A2.0!")})
    c.run("create 1")
    c.run("create 2")

    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import copy
        class Pkg(ConanFile):
            name = "liba"
            version = "3.0"

            def requirements(self):
                # To avoid conflict among liba versions
                self.requires("liba/1.0", headers=False, libs=False, visible=False)
                self.requires("liba/2.0", visible=False)

            def package(self):
                for _, dep in self.dependencies.items():
                    copy(self, "*", src=dep.package_folder, dst=self.package_folder)
        """)
    c.save({"conanfile.py": conanfile})
    c.run("create .")

    c.run("install --requires=liba/3.0 --deployer=full_deploy")
    assert re.search(r"Skipped binaries(\s*)liba/1.0, liba/2.0", c.out)
    assert "liba/3.0: Already installed!" in c.out
    assert c.load("full_deploy/host/liba/3.0/a1.txt") == "A1.0!"
    assert c.load("full_deploy/host/liba/3.0/a2.txt") == "A2.0!"


def test_repackage_library_self_transitive():
    c = TestClient()
    c.save({"a/conanfile.py": GenConanfile("liba", "1.0").with_package_file("a1.txt", "A1.0!"),
            "b/conanfile.py": GenConanfile("libb", "1.0").with_requires("liba/1.0")})
    c.run("create a")
    c.run("create b")

    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import copy
        class Pkg(ConanFile):
            name = "liba"
            version = "3.0"

            def requirements(self):
                # libs=True, otherwise transitive liba is skipped
                self.requires("libb/1.0", headers=False, libs=True, visible=False, run=False)

            def package(self):
                for _, dep in self.dependencies.items():
                    copy(self, "*", src=dep.package_folder, dst=self.package_folder)
        """)
    c.save({"conanfile.py": conanfile})
    c.run("create .")

    c.run("install --requires=liba/3.0 --deployer=full_deploy")
    assert re.search(r"Skipped binaries(\s*)liba/1.0, libb/1.0", c.out)
    assert "liba/3.0: Already installed!" in c.out
    assert c.load("full_deploy/host/liba/3.0/a1.txt") == "A1.0!"
