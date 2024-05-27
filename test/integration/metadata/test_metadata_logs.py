import os
import textwrap

import pytest

from conans.model.recipe_ref import RecipeReference
from conan.test.utils.tools import TestClient
from conans.util.files import load, save


class TestRecipeMetadataLogs:

    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import save, copy

        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"

            def export(self):
                copy(self, "*.log", src=self.recipe_folder,
                dst=os.path.join(self.recipe_metadata_folder, "logs"))

            def layout(self):
                self.folders.build = "mybuild"
                self.folders.generators = "mybuild/generators"

            def source(self):
                save(self, os.path.join(self.recipe_metadata_folder, "logs", "src.log"), "srclog!!")

            def build(self):
                save(self, "mylogs.txt", "some logs!!!")
                copy(self, "mylogs.txt", src=self.build_folder,
                dst=os.path.join(self.package_metadata_folder, "logs"))
        """)

    def test_metadata_logs(self):
        c = TestClient(default_server_user=True)
        c.save({"conanfile.py": self.conanfile,
                "file.log": "log contents!"})
        c.run("create .")
        # Test local cache looks good
        ref = RecipeReference.loads("pkg/0.1")
        ref_layout = c.get_latest_ref_layout(ref)
        assert os.listdir(ref_layout.metadata()) == ["logs"]
        assert set(os.listdir(os.path.join(ref_layout.metadata(), "logs"))) == {"file.log",
                                                                                "src.log"}
        assert load(os.path.join(ref_layout.metadata(), "logs", "file.log")) == "log contents!"
        assert load(os.path.join(ref_layout.metadata(), "logs", "src.log")) == "srclog!!"

        pref = c.get_latest_package_reference(ref)
        pref_layout = c.get_latest_pkg_layout(pref)
        assert os.listdir(pref_layout.metadata()) == ["logs"]
        assert os.listdir(os.path.join(pref_layout.metadata(), "logs")) == ["mylogs.txt"]
        assert load(os.path.join(pref_layout.metadata(), "logs", "mylogs.txt")) == "some logs!!!"

    def test_metadata_logs_local(self):
        c = TestClient(default_server_user=True)
        c.save({"conanfile.py": self.conanfile,
                "file.log": "log contents!"})
        c.run("source .")
        assert c.load("metadata/logs/src.log") == "srclog!!"
        c.run("build .")
        assert c.load("mybuild/metadata/logs/mylogs.txt") == "some logs!!!"

    def test_download_pkg_list_from_graph(self):
        c = TestClient(default_server_user=True)
        c.save({"conanfile.py": self.conanfile,
                "file.log": "log contents!"})
        c.run("create .")
        c.run("upload * -r=default -c")
        c.run("remove * -c")
        #  IMPORTANT: NECESSARY to force the download to gather the full package_list
        # TODO: Check the case how to download metadata for already installed in cache packages
        c.run("install --requires=pkg/0.1 --format=json", redirect_stdout="graph.json")
        c.run("list --graph=graph.json --format=json", redirect_stdout="pkglist.json")
        # This list will contain both "Local Cache" and "default" origins, because it was downloaded
        c.run("download --list=pkglist.json -r=default --metadata=*")

        ref = RecipeReference.loads("pkg/0.1")
        pref = c.get_latest_package_reference(ref)
        pref_layout = c.get_latest_pkg_layout(pref)
        assert os.listdir(pref_layout.metadata()) == ["logs"]
        assert os.listdir(os.path.join(pref_layout.metadata(), "logs")) == ["mylogs.txt"]
        assert load(os.path.join(pref_layout.metadata(), "logs", "mylogs.txt")) == "some logs!!!"

    def test_metadata_folder_exist(self):
        """ make sure the folders exists
        so recipe don't have to create it for running bulk copies calling self.run(cp -R)
        """
        conanfile = textwrap.dedent("""
            import os
            from conan import ConanFile

            class Pkg(ConanFile):
                name = "pkg"
                version = "0.1"

                def export(self):
                    assert os.path.exists(self.recipe_metadata_folder)

                def source(self):
                    assert os.path.exists(self.recipe_metadata_folder)

                def build(self):
                    assert os.path.exists(self.package_metadata_folder)
            """)
        c = TestClient(default_server_user=True)
        c.save({"conanfile.py": conanfile})
        c.run("create .")
        c.run("upload * -r=default -c")
        c.run("remove * -c")
        c.run("install --requires=pkg/0.1 --build=*")
        # If nothing fail, all good, all folder existed, assert passed


class TestHooksMetadataLogs:

    @pytest.fixture()
    def _client(self):
        c = TestClient(default_server_user=True)
        my_hook = textwrap.dedent("""\
            import os
            from conan.tools.files import copy

            def post_export(conanfile):
                conanfile.output.info("post_export")
                copy(conanfile, "*.log", src=conanfile.recipe_folder,
                     dst=os.path.join(conanfile.recipe_metadata_folder, "logs"))

            def post_source(conanfile):
                conanfile.output.info("post_source")
                copy(conanfile, "*", src=os.path.join(conanfile.source_folder, "logs"),
                     dst=os.path.join(conanfile.recipe_metadata_folder, "logs"))

            def post_build(conanfile):
                conanfile.output.info("post_build")
                copy(conanfile, "*", src=os.path.join(conanfile.build_folder, "logs"),
                     dst=os.path.join(conanfile.package_metadata_folder, "logs"))
            """)
        hook_path = os.path.join(c.cache.hooks_path, "my_hook", "hook_my_hook.py")
        save(hook_path, my_hook)
        conanfile = textwrap.dedent("""
            import os
            from conan import ConanFile
            from conan.tools.files import save, copy

            class Pkg(ConanFile):
                name = "pkg"
                version = "0.1"
                no_copy_source = True

                def layout(self):
                    self.folders.build = "mybuild"
                    self.folders.generators = "mybuild/generators"

                def source(self):
                    save(self, "logs/src.log", "srclog!!")

                def build(self):
                    save(self, "logs/mylogs.txt", "some logs!!!")
            """)
        c.save({"conanfile.py": conanfile,
                "file.log": "log contents!"})
        return c

    def test_metadata_logs_hook(self, _client):
        c = _client
        c.run("create .")
        # Test local cache looks good
        ref = RecipeReference.loads("pkg/0.1")
        ref_layout = c.get_latest_ref_layout(ref)
        assert os.listdir(ref_layout.metadata()) == ["logs"]
        assert set(os.listdir(os.path.join(ref_layout.metadata(), "logs"))) == {"file.log",
                                                                                "src.log"}
        assert load(os.path.join(ref_layout.metadata(), "logs", "file.log")) == "log contents!"
        assert load(os.path.join(ref_layout.metadata(), "logs", "src.log")) == "srclog!!"

        pref = c.get_latest_package_reference(ref)
        pref_layout = c.get_latest_pkg_layout(pref)
        assert os.listdir(pref_layout.metadata()) == ["logs"]
        assert os.listdir(os.path.join(pref_layout.metadata(), "logs")) == ["mylogs.txt"]
        assert load(os.path.join(pref_layout.metadata(), "logs", "mylogs.txt")) == "some logs!!!"

    def test_metadata_logs_local(self, _client):
        c = _client
        c.run("source .")
        assert c.load("metadata/logs/src.log") == "srclog!!"
        c.run("build .")
        assert c.load("mybuild/metadata/logs/mylogs.txt") == "some logs!!!"


def test_metadata_export_pkg():
    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import save, copy

        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"

            def build(self):
                save(self, "mylogs.txt", "some logs!!!")
                copy(self, "mylogs.txt", src=self.build_folder,
                     dst=os.path.join(self.package_metadata_folder, "logs"))

            def package(self):
                copy(self, "*", src=os.path.join(self.build_folder, "metadata"),
                     dst=self.package_metadata_folder)
        """)

    c = TestClient()
    c.save({"conanfile.py": conanfile})
    c.run("build .")
    c.run("export-pkg .")
    # Test local cache looks good
    pkg_layout = c.created_layout()
    assert os.listdir(pkg_layout.metadata()) == ["logs"]
    assert os.listdir(os.path.join(pkg_layout.metadata(), "logs")) == ["mylogs.txt"]
    assert load(os.path.join(pkg_layout.metadata(), "logs", "mylogs.txt")) == "some logs!!!"
