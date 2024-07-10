import os
import textwrap

import pytest

from conan.test.assets.genconanfile import GenConanfile

from conan.test.utils.tools import TestClient


class TestLocalFlows:

    @pytest.fixture
    def client():
        tc = TestClient(light=True)
        tc.save({"dep/conanfile.py": textwrap.dedent("""
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

            def package_info(self):
                self.output.info(f"Running package_info method in {self.package_folder}")
        """)})
        tc.run("export dep")
        return tc


    def test_basic_install_method(client):
        client.run("create dep")
        layout = client.created_layout()
        assert layout.package().endswith("p")
        assert f"Package folder {layout.package()}" in client.out
        assert f"Running install method in {layout.install()}" in client.out
        assert f"Running package_info method in {layout.install()}" in client.out
        client.run("install --requires=dep/1.0")
        assert f"Running package_info method in {layout.install()}" in client.out


    @pytest.mark.parametrize("build_missing", [True, False])
    def test_dependency_install_method(client, build_missing):
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
        if not build_missing:
            client.run("create dep")
        build_flag = "--build=missing" if build_missing else ""
        client.run(f"create app {build_flag}")
        # Dep package folder: /private/var/folders/lw/6bflvp3s3t5b56n2p_bj_vx80000gn/T/tmpy1wku27hconans/path with spaces/.conan2/p/b/depadc6c4067b602/i
        # TODO: Check that the package_folder printed here is the installed folder, not the package folder


class TestRemoteFlows:
    def test_remote_upload_install_method():
        tc = TestClient(light=True, default_server_user=True)
        conanfile = textwrap.dedent("""
                import os
                from conan import ConanFile
                from conan.tools.files import save, copy

                class TestConan(ConanFile):
                    name = "dep"
                    version = "1.0"
                    def package(self):
                        save(self, os.path.join(self.package_folder, "file.txt"), "Hello World! - {}")

                    def install(self):
                        self.output.info(f"Running install method in {self.install_folder}")
                        # copy(self, "*", src=self.package_folder, dst=self.install_folder)
                        copy(self, "file.txt", src=self.package_folder, dst=self.install_folder)
                        save(self, os.path.join(self.install_folder, "installed.txt"), "Installed file")

                    def package_info(self):
                        self.output.info(f"Running package_info method in {self.package_folder}")
                """)
        tc.save({"conanfile.py": conanfile})
        tc.run("create .")
        created_package = tc.created_package_reference("dep/1.0")
        tc.run("upload * -r=default -c")
        # TODO: Check what is in the server - it ought to be the real package folder, not the install folder
        print()
        tc.run("remove * -c")
        tc.run(f"download {created_package} -r=default")
        # No install folder yet because it has not been used in any graph, we just get the normal package folder

        print()
        tc.run(f"cache path {created_package}")
        package_folder = tc.out.strip()
        assert package_folder.endswith("p")
        assert "file.txt" in os.listdir(package_folder)
        assert "installed.txt" not in os.listdir(package_folder)
        assert not os.path.exists(os.path.join(package_folder, "..", "i"))
        # Now this install will run the install method
        tc.run("install --requires=dep/1.0")

        tc.run("remove * -c")
        tc.run("install --requires=dep/1.0 -r=default")
        print()
