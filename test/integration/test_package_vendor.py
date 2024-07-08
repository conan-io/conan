import os
import textwrap

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def test_package_vendor():
    c = TestClient()
    app = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import copy, save

        class App(ConanFile):
            name = "app"
            version = "0.1"
            package_type = "application"
            vendor = True
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
    c.run("create app")  # -c tools.graph:vendor=build will be automatic
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
    c.run("install --requires=app/0.1 --deployer=full_deploy -c tools.graph:vendor=build")
    assert "pkga" in c.out
    assert c.load("full_deploy/host/app/0.1/app.exe") == "app"
    assert c.load("full_deploy/host/app/0.1/pkga.dll") == "dll"

    # and finally we can force the expansion and the rebuild
    c.run("install --requires=app/0.1 --build=app* --deployer=full_deploy "
          "-c tools.graph:vendor=build")
    assert "pkga" in c.out
    assert c.load("full_deploy/host/app/0.1/app.exe") == "app"
    assert c.load("full_deploy/host/app/0.1/pkga.dll") == "newdll"
    # This shoulnd't happen, no visibility over transitive dependencies of app
    assert not os.path.exists(os.path.join(c.current_folder, "full_deploy", "host", "pkga"))

    # lets remove the binary
    c.run("remove app:* -c")
    c.run("install --requires=app/0.1", assert_error=True)
    assert "Missing binary" in c.out
    c.run("install --requires=app/0.1 --build=missing", assert_error=True)
    assert "app/0.1: Invalid: The package 'app/0.1' is a vendoring one, needs to be built " \
           "from source, but it didn't enable 'tools.graph:vendor=build'" in c.out

    c.run("install --requires=app/0.1 --build=missing  -c tools.graph:vendor=build")
    assert "pkga" in c.out  # it works


def test_package_vendor_editable():
    c = TestClient()
    pkgb = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import copy, save

        class App(ConanFile):
            name = "pkgb"
            version = "0.1"
            package_type = "shared-library"
            vendor = True
            requires = "pkga/0.1"
            def layout(self):
                self.folders.build = "build"
                self.cpp.build.bindirs = ["build"]
            def generate(self):
                copy(self, "*", src=self.dependencies["pkga"].package_folder,
                     dst=self.build_folder)
            def build(self):
                save(self, os.path.join(self.build_folder, "pkgb.dll"), "dll")
            """)

    c.save({"pkga/conanfile.py": GenConanfile("pkga", "0.1").with_package_type("shared-library")
                                                            .with_package_file("bin/pkga.dll", "d"),
            "pkgb/conanfile.py": pkgb,
            "app/conanfile.py": GenConanfile("app", "0.1").with_settings("os")
                                                          .with_requires("pkgb/0.1")
            })
    c.run("create pkga")
    c.run("editable add pkgb")
    c.run("install app -s os=Linux")
    assert "pkga" in c.out
    # The environment file of "app" doesn't have any visibility of the "pkga" paths
    envfile_app = c.load("app/conanrunenv.sh")
    assert "pkga" not in envfile_app
    # But the environment file needed to build "pkgb" has visibility over the "pkga" paths
    envfile_pkgb = c.load("pkgb/conanrunenv.sh")
    assert "pkga" in envfile_pkgb


def test_vendor_dont_propagate_options():
    c = TestClient()
    app = GenConanfile("app", "0.1").with_requires("pkga/0.1").with_class_attribute("vendor=True")
    c.save({"pkga/conanfile.py": GenConanfile("pkga", "0.1").with_shared_option(False),
            "app/conanfile.py": app,
            "consumer/conanfile.txt": "[requires]\napp/0.1",
            "consumer_shared/conanfile.txt": "[requires]\napp/0.1\n[options]\n*:shared=True"
            })
    c.run("create pkga")
    c.assert_listed_binary({"pkga/0.1": ("55c609fe8808aa5308134cb5989d23d3caffccf2", "Build")})
    c.run("create app")
    c.assert_listed_binary({"pkga/0.1": ("55c609fe8808aa5308134cb5989d23d3caffccf2", "Cache"),
                            "app/0.1": ("da39a3ee5e6b4b0d3255bfef95601890afd80709", "Build")})
    c.run("install consumer --build=app/* -c tools.graph:vendor=build")
    c.assert_listed_binary({"pkga/0.1": ("55c609fe8808aa5308134cb5989d23d3caffccf2", "Cache"),
                            "app/0.1": ("da39a3ee5e6b4b0d3255bfef95601890afd80709", "Build")})
    c.run("install consumer_shared --build=app/* -c tools.graph:vendor=build")
    c.assert_listed_binary({"pkga/0.1": ("55c609fe8808aa5308134cb5989d23d3caffccf2", "Cache"),
                            "app/0.1": ("da39a3ee5e6b4b0d3255bfef95601890afd80709", "Build")})


def test_package_vendor_export_pkg():
    c = TestClient()
    app = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import copy, save

        class App(ConanFile):
            name = "app"
            version = "0.1"
            package_type = "application"
            vendor = True
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
    c.run("build app")  # -c tools.graph:vendor=build will be automatic
    c.run("export-pkg app")
    assert "pkga/0.1" in c.out  # In the export-pkg process, dependencies are still needed
    assert "conanfile.py (app/0.1): package(): Packaged 1 '.dll' file: pkga.dll" in c.out

    # we can safely remove pkga, once the package is created, it can work without deps
    c.run("remove pkg* -c")
    c.run("list app:*")
    assert "pkga" not in c.out  # The binary doesn't depend on pkga
    c.run("install --requires=app/0.1 --deployer=full_deploy")
    assert "pkga" not in c.out
    assert c.load("full_deploy/host/app/0.1/app.exe") == "app"
    assert c.load("full_deploy/host/app/0.1/pkga.dll") == "dll"
