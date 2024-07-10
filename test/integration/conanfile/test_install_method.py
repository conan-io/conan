import os
import textwrap

import pytest

from conan.test.assets.genconanfile import GenConanfile

from conan.test.utils.tools import TestClient
from conans.util.files import load

conanfile_dep = textwrap.dedent("""
    import os
    from conan import ConanFile
    from conan.tools.files import save, copy

    class TestConan(ConanFile):
        name = "dep"
        version = "1.0"
        def package(self):
            save(self, os.path.join(self.package_folder, "file.txt"), "Hello World!")

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
                    save(self, os.path.join(self.install_folder, "installed.txt"), "Installed file")

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
        assert f"Running install method in {downloaded_pref_layout.install()}" in client.out


class TestEditableFlows:
    @pytest.fixture
    def client(self):
        tc = TestClient(light=True)
        tc.save({"dep/conanfile.py": conanfile_dep})
        return tc

    def test_editable_install_method(self, client):
        client.run("editable add dep")
        # If we try to consume it, it will run the install() method
        client.run("install --requires=dep/1.0")
        # TODO: Make this not fail
        assert "Running install method in" in client.out

