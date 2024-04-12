import textwrap

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_repackage():
    c = TestClient()
    app = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import copy, save

        class App(ConanFile):
            name = "app"
            version = "0.1"
            package_type = "application"
            repackage = True
            requires = "pkga/0.1"
            def package(self):
                copy(self, "*", src=self.dependencies["pkga"].package_folder,
                     dst=self.package_folder)
                save(self, os.path.join(self.package_folder, "app.exe"), "app")
            """)

    c.save({"pkga/conanfile.py": GenConanfile("pkga", "0.1").with_package_type("shared-library")
                                                            .with_package_file("pkga.dll", "dll"),
            "app/conanfile.py": app
            })
    c.run("create pkga")
    c.run("create app")  # -c tools.graph:repackage=True will be automatic
    assert "app/0.1: package(): Packaged 1 '.dll' file: pkga.dll" in c.out

    # we can safely remove pkga
    c.run("remove pkg* -c")
    c.run("list app:*")
    assert "pkga" not in c.out  # The binary doesn't depend on pkga
    c.run("install --requires=app/0.1 --deployer=full_deploy")
    assert "pkga" not in c.out
    assert c.load("full_deploy/host/app/0.1/app.exe") == "app"
    assert c.load("full_deploy/host/app/0.1/pkga.dll") == "dll"

    # we can create a modified pkga
    c.save({"pkga/conanfile.py": GenConanfile("pkga", "0.1").with_package_type("shared-library")
           .with_package_file("pkga.dll", "newdll")})
    c.run("create pkga")
    # still using the re-packaged one
    c.run("install --requires=app/0.1 --deployer=full_deploy")
    assert "pkga" not in c.out
    assert c.load("full_deploy/host/app/0.1/app.exe") == "app"
    assert c.load("full_deploy/host/app/0.1/pkga.dll") == "dll"

    # but we can force the expansion, still not the rebuild
    c.run("install --requires=app/0.1 --deployer=full_deploy -c tools.graph:repackage=True")
    assert "pkga" in c.out
    assert c.load("full_deploy/host/app/0.1/app.exe") == "app"
    assert c.load("full_deploy/host/app/0.1/pkga.dll") == "dll"

    # and finally we can force the expansion and the rebuild
    c.run("install --requires=app/0.1 --build=app* --deployer=full_deploy "
          "-c tools.graph:repackage=True")
    assert "pkga" in c.out
    assert c.load("full_deploy/host/app/0.1/app.exe") == "app"
    assert c.load("full_deploy/host/app/0.1/pkga.dll") == "newdll"

    # lets remove the binary
    c.run("remove app:* -c")
    c.run("install --requires=app/0.1", assert_error=True)
    assert "Missing binary" in c.out
    c.run("install --requires=app/0.1 --build=missing", assert_error=True)
    assert "ERROR: The package 'app/0.1' is repackaging and building but it didn't " \
           "enable 'tools.graph:repackage'" in c.out
    c.run("install --requires=app/0.1 --build=missing  -c tools.graph:repackage=True")
    assert "pkga" in c.out  # it works
