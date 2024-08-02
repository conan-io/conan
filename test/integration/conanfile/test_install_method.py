import json
import os
import textwrap

import pytest

from conan.test.assets.genconanfile import GenConanfile

from conan.test.utils.tools import TestClient
from conans.util.files import load, save

conanfile_dep = textwrap.dedent("""
    import os
    from conan import ConanFile
    from conan.tools.files import save, copy

    class TestConan(ConanFile):
        name = "dep"
        version = "1.0"
        def package(self):
            save(self, os.path.join(self.package_folder, "file.txt"), "Hello World!")
            save(self, os.path.join(self.package_folder, "file2.txt"), "Hello World 2!")

        def install(self):
            self.output.info(f"Running install method in {self.install_folder}")
            # copy(self, "*", src=self.package_folder, dst=self.install_folder)
            copy(self, "file.txt", src=self.package_folder, dst=self.install_folder)
            save(self, os.path.join(self.install_folder, "installed.txt"), "Installed file")

        def package_info(self):
            self.output.info(f"Running package_info method in {self.package_folder}")
    """)


class TestBasicLocalFlows:

    @pytest.fixture
    def client(self):
        tc = TestClient(light=True)
        tc.save({"dep/conanfile.py": conanfile_dep})
        tc.run("export dep")
        return tc

    def test_basic_install_method(self, client):
        client.run("create dep")
        layout = client.created_layout()
        assert layout.package().endswith("p")
        assert f"Package folder {layout.package()}" in client.out
        assert f"Running install method in {layout.install()}" in client.out
        assert f"Running package_info method in {layout.install()}" in client.out
        client.run("install --requires=dep/1.0")
        assert f"Running package_info method in {layout.install()}" in client.out
        # Only issue is that the PackageLayout has no idea about the redirected package folder
        # So we have to know to check for it in tests, but oh well
        assert "installed.txt" in os.listdir(layout.install())
        assert "installed.txt" not in os.listdir(layout.package())

    def test_dependency_install_method(self, client):
        client.save({"app/conanfile.py": textwrap.dedent("""
                 from conan import ConanFile
                 class TestConan(ConanFile):
                     name = "app"
                     version = "1.0"
                     requires = "dep/1.0"
                     def generate(self):
                         self.output.info("Running generate method")
                         dep_pkg_folder = self.dependencies["dep"].package_folder
                         self.output.info(f"Dep package folder: {dep_pkg_folder}")
                 """)})
        client.run("create dep")
        dep_layout = client.created_layout()
        client.run("create app")
        assert f"Dep package folder: {dep_layout.package()}" not in client.out
        assert f"Dep package folder: {dep_layout.install()}" in client.out

    def test_no_non_info_access(self):
        client = TestClient(light=True)
        client.save({"conanfile.py": GenConanfile("dep", "1.0")
                     .with_install("self.output.info('settings.os: ' + self.settings.os)")})
        client.run("create .", assert_error=True)
        assert "'self.settings' access in 'install()' method is forbidden" in client.out

    def test_install_moves_from_package(self):
        client = TestClient(light=True)
        client.save({"conanfile.py": GenConanfile("dep", "1.0")
                     .with_import("from conan.tools.files import save, rename",
                                  "import os")
                     .with_option("move", [True, False])
                     .with_package('save(self, os.path.join(self.package_folder, "file.txt"), "Hello World!")',
                                   "save(self, os.path.join(self.package_folder, 'file2.txt'), 'Hello World 2!')")
                     # This is NOT allowed, moving from package to install is forbidden, only as test to ensure consistency
                     .with_install("rename(self, os.path.join(self.package_folder, 'file.txt'), os.path.join(self.install_folder, 'file.txt')) if self.info.options.move else None")})
        client.run("create . -o=dep/*:move=True")
        dep_moved_layout = client.created_layout()
        dep_moved_pkgid = client.created_package_id("dep/1.0")
        assert "file.txt" in os.listdir(dep_moved_layout.install())
        assert "file.txt" not in os.listdir(dep_moved_layout.package())

        client.run("create . -o=dep/*:move=False")
        dep_kept_layout = client.created_layout()
        dep_kept_pkgid = client.created_package_id("dep/1.0")
        assert "file.txt" not in os.listdir(dep_kept_layout.install())
        assert "file.txt" in os.listdir(dep_kept_layout.package())

        # Now we can check that the package_id is the same for both
        assert dep_moved_pkgid != dep_kept_pkgid

    def test_cache_path_command(self, client):
        client.run("create dep")
        dep_layout = client.created_layout()
        pref = client.created_package_reference("dep/1.0")
        client.run(f"cache path {pref}")
        assert dep_layout.package() not in client.out
        assert dep_layout.install() in client.out

    def test_remove_deletes_correct_folders(self, client):
        client.run("create dep")
        dep_layout = client.created_layout()
        client.run("remove * -c")
        assert not os.path.exists(dep_layout.package())
        assert not os.path.exists(dep_layout.install())

    def test_save_restore_cache(self, client):
        # Not created in the cache, just exported, nothing breaks because there is not even a package there
        client.run("cache save *:*")
        client.run("remove * -c")
        client.run("cache restore conan_cache_save.tgz")

        # Now create the package and then save/restore
        client.run("create dep")
        dep_layout = client.created_layout()
        client.run("cache save *:* -f=json", redirect_stdout="saved.json")
        saved = json.loads(client.load("saved.json"))
        pref = dep_layout.reference
        saved_pkg_folder = saved["Local Cache"]["dep/1.0"]["revisions"][pref.ref.revision]["packages"][pref.package_id]["revisions"][pref.revision]["package_folder"]
        assert saved_pkg_folder in dep_layout.package().replace("\\", "/")
        client.run("remove * -c")
        assert not os.path.exists(dep_layout.package())
        assert not os.path.exists(dep_layout.install())
        client.run("cache restore conan_cache_save.tgz")
        client.run(f"cache path {dep_layout.reference}")
        package_folder = client.out.strip()

        # The install() folder does not exist as restoring is not considered usage, so it never runs
        # so this is just the immutable package_folder
        assert "installed.txt" not in os.listdir(package_folder)

        # But as soon as you call conan install, install() is called and so it's used,
        # so package_folder will be the install folder
        client.run("install --requires=dep/1.0")
        client.run(f"cache path {dep_layout.reference}")
        package_folder = client.out.strip()
        assert "installed.txt" in os.listdir(package_folder)

    def test_graph_info_output(self, client):
        client.run("create dep")
        dep_layout = client.created_layout()
        client.run("install --requires=dep/1.0 -f=json", redirect_stdout="install.json")
        install_output = json.loads(client.load("install.json"))
        assert install_output["graph"]["nodes"]["1"]["package_folder"] == dep_layout.install()
        assert install_output["graph"]["nodes"]["1"]["immutable_package_folder"] == dep_layout.package()

    def test_create_pkglist_output(self, client):
        client.run("create dep -f=json", redirect_stdout="created.json")
        created_pkgid = client.created_package_id("dep/1.0")
        client.run("list --graph=created.json --graph-binaries=build")
        assert created_pkgid in client.out

    def test_vendorized_basic(self, client):
        client.run("create dep")
        client.save({"vendor/conanfile.py": GenConanfile("vendor", "1.0")
                     .with_import("from conan.tools.files import copy")
                     .with_class_attribute("vendor=True")
                     .with_requires("dep/1.0")
                     .with_package("copy(self, 'file.txt', src=self.dependencies['dep'].package_folder, dst=self.package_folder)",
                                   "copy(self, 'installed.txt', src=self.dependencies['dep'].package_folder, dst=self.package_folder)",
                                   "copy(self, 'file2.txt', src=self.dependencies['dep'].immutable_package_folder, dst=self.package_folder)")})
        client.run("create vendor")
        vendor_layout = client.created_layout()
        assert "file.txt" in os.listdir(vendor_layout.package())
        assert "installed.txt" in os.listdir(vendor_layout.package())
        assert "file2.txt" in os.listdir(vendor_layout.package())

        client.save("app/conanfile.py", GenConanfile("app", "1.0")
                    .with_requires("vendor/1.0"))

    def test_check_integrity(self, client):
        client.run("create dep")
        dep_layout = client.created_layout()
        client.run(f"cache check-integrity {dep_layout.reference}")
        assert "There are corrupted artifacts" not in client.out
        # Even if we re-change the install folder contents, it should still be fine
        save(os.path.join(dep_layout.install(), "installed.txt"), "Modified!")
        client.run(f"cache check-integrity {dep_layout.reference}")
        assert "There are corrupted artifacts" not in client.out
        # But as soon as we change the package, it should still fail like a normal package would
        save(os.path.join(dep_layout.package(), "file.txt"), "Modified!")
        client.run(f"cache check-integrity {dep_layout.reference}", assert_error=True)
        assert "There are corrupted artifacts" in client.out

    @pytest.mark.parametrize("with_install_method", [True, False])
    def test_access_immutable_from_consumer(self, client, with_install_method):
        if not with_install_method:
            client.save({"dep/conanfile.py": GenConanfile("dep", "1.0")})
        client.save({"app/conanfile.py": GenConanfile("app", "1.0")
                     .with_requires("dep/1.0")
                     .with_package("dep = self.dependencies['dep/1.0']",
                                   "self.output.info(f'Immutable package: {dep.immutable_package_folder}')",
                                   # TODO: Think about if we want this interface
                                   # "self.output.info(f'Install: {dep.install_folder}')",
                                   "self.output.info(f'Package: {dep.package_folder}')")})
        client.run("create dep")
        dep_layout = client.created_layout()
        client.run("create app")
        assert f"app/1.0: Immutable package: {dep_layout.package()}" in client.out
        # assert f"app/1.0: Install: {dep_layout.install()}" in client.out
        if with_install_method:
            assert f"app/1.0: Package: {dep_layout.install()}" in client.out
        else:
            assert f"app/1.0: Package: {dep_layout.package()}" in client.out

    def test_cache_modification_of_custom_conf_based_on_settings(self):
        tc = TestClient(light=True)
        tc.save({"conanfile.py": GenConanfile("dep", "1.0")
                .with_import("from conan.tools.files import save",
                             "import os")
                .with_option("myoption", [True, False])
                .with_option("otheroption", [True, False])
                .with_default_option("myoption", False)
                .with_default_option("otheroption", False)
                .with_setting("os")
                .with_package_id("del self.info.options.myoption")
                .with_install("save(self, os.path.join(self.install_folder, 'file.txt'), 'Hello World!')",
                              "save(self, os.path.join(self.install_folder, 'os.conf'), str(self.info.settings.os))",
                              "save(self, os.path.join(self.install_folder, 'option.conf'), str(self.info.options.get_safe('myoption')))",
                              "save(self, os.path.join(self.install_folder, 'otheroption.conf'), str(self.info.options.otheroption))")})
        tc.run("create . -s=os=Linux -o=&:myoption=True -o=&:otheroption=True")
        layout = tc.created_layout()
        assert "file.txt" in os.listdir(layout.install())
        assert tc.load(os.path.join(layout.install(), "os.conf")) == "Linux"
        # This is problematic, it means that the mapping for install() and package_id would not be 1:1 and could be outdated
        assert tc.load(os.path.join(layout.install(), "option.conf")) == "None"
        assert tc.load(os.path.join(layout.install(), "otheroption.conf")) == "True"


class TestToolRequiresFlows:
    def test_tool_requires(self):
        tc = TestClient(light=True)
        tc.save({"dep/conanfile.py": textwrap.dedent("""
            import os
            from conan import ConanFile
            from conan.tools.files import save, copy

            class TestConan(ConanFile):
                name = "dep"
                version = "1.0"
                package_type = "application"
                def package(self):
                    save(self, os.path.join(self.package_folder, "bin", "executable.txt"), "Base")

                def install(self):
                    self.output.info(f"Running install method in {self.install_folder}")
                    copy(self, "*", src=self.package_folder, dst=self.install_folder)
                    save(self, os.path.join(self.install_folder, "bin", "installed.txt"), "Installed file")

                def package_info(self):
                    self.output.info(f"Running package_info method in {self.package_folder}")
                    self.cpp_info.bindirs = ["bin"]

            """), "app/conanfile.py": textwrap.dedent("""
            from conan import ConanFile
            import os

            class TestConan(ConanFile):
                name = "app"
                version = "1.0"

                def build_requirements(self):
                    self.tool_requires("dep/1.0")

                def build(self):
                    self.output.info("Running build method")
                    bindir = self.dependencies.build['dep'].cpp_info.bindir
                    self.output.info(f"Dep bindir: {bindir}")
                    self.output.info(f"Is installed? {os.path.exists(os.path.join(bindir, 'installed.txt'))}")
            """)})
        tc.run("create dep --build-require")
        dep_layout = tc.created_layout()
        tc.run("create app")
        # This fails. cpp_info is using the original package folder to construct the final path
        assert f"Dep bindir: {dep_layout.install()}" in tc.out
        assert "app/1.0: Is installed? True" in tc.out

    def test_test_package_uses_created_tool_which_modifies_pkgfolder(self):
        tc = TestClient(light=True)
        tc.save({"conanfile.py": GenConanfile("app", "1.0")
                .with_import("from conan.tools.files import save")
                .with_package_type("application")
                .with_package("save(self, 'file.txt', 'Hello World!')")
                .with_package_info({"bindirs": ["bin"]}, {})
                .with_install("save(self, 'installed.txt', 'Installed file')"),
                 "test_package/conanfile.py": GenConanfile()
                .with_import("from conan.tools.files import save",
                             "import os")
                .with_test_reference_as_build_require()
                .with_test("bindir = self.dependencies.build[self.tested_reference_str].cpp_info.bindir",
                           "self.output.info(f'Bindir: {bindir}')",
                           "save(self, os.path.join(bindir, '__pycache__.pyc'), 'Test file')")})
        tc.run("create . --build-require")
        app_layout = tc.created_layout()
        assert f"Bindir: {os.path.join(app_layout.install(), 'bin')}" in tc.out
        tc.run(f"cache check-integrity {app_layout.reference}")
        assert "There are corrupted artifacts" not in tc.out


class TestRemoteFlows:

    @pytest.fixture
    def client(self):
        tc = TestClient(light=True, default_server_user=True)
        tc.save({"dep/conanfile.py": conanfile_dep})
        tc.run("export dep")
        return tc

    def test_remote_upload_install_method(self, client):
        client.run("create dep")
        created_pref = client.created_package_reference("dep/1.0")
        client.run("upload * -r=default -c")

        # Only the package folder is uploaded, not the install folder
        uploaded_pref_path = client.servers["default"].test_server.server_store.package(created_pref)
        manifest_contents = load(os.path.join(uploaded_pref_path, "conanmanifest.txt"))
        assert "file.txt" in manifest_contents
        assert "installed.txt" not in manifest_contents

        client.run("remove * -c")
        client.run(f"download {created_pref} -r=default")
        downloaded_pref_layout = client.get_latest_pkg_layout(created_pref)
        assert "file.txt" in os.listdir(downloaded_pref_layout.package())
        # Download is not an "usage" of the package, so no install() is yet executed
        assert "installed.txt" not in os.listdir(downloaded_pref_layout.package())
        assert not os.path.exists(os.path.join(downloaded_pref_layout.install()))

        client.run(f"cache path {created_pref}")
        package_folder = client.out.strip()
        assert package_folder == downloaded_pref_layout.package()
        assert package_folder.endswith("p")
        # Now this install will run the install() method
        client.run("install --requires=dep/1.0")
        assert f"Running install method in {downloaded_pref_layout.install()}" in client.out

        client.run("remove * -c")
        client.run("install --requires=dep/1.0 -r=default")
        assert "dep/1.0: Calling install()"
        assert f"Running install method in {downloaded_pref_layout.install()}" in client.out

    def test_upload_verify_integrity(self, client):
        client.run("create dep")
        dep_layout = client.created_layout()
        client.run("upload * -r=default -c --check")
        assert f"dep/1.0:{dep_layout.reference.package_id}: Integrity checked: ok" in client.out
        assert "There are corrupted artifacts" not in client.out
