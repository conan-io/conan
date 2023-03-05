import os
import textwrap

import pytest

from conans.model.recipe_ref import RecipeReference
from conans.test.utils.tools import TestClient
from conans.util.files import load, save


def test_metadata_logs():
    c = TestClient(default_server_user=True)
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

            def source(self):
                save(self, os.path.join(self.recipe_metadata_folder, "logs", "src.log"), "srclog!!")

            def build(self):
                save(self, "mylogs.txt", "some logs!!!")
                copy(self, "mylogs.txt", src=self.build_folder,
                     dst=os.path.join(self.pkg_metadata_folder, "logs"))
        """)
    c.save({"conanfile.py": conanfile,
            "file.log": "log contents!"})
    c.run("create .")
    # Test local cache looks good
    ref = RecipeReference.loads("pkg/0.1")
    ref_layout = c.get_latest_ref_layout(ref)
    assert os.listdir(ref_layout.metadata()) == ["logs"]
    assert os.listdir(os.path.join(ref_layout.metadata(), "logs")) == ["file.log", "src.log"]
    assert load(os.path.join(ref_layout.metadata(), "logs", "file.log")) == "log contents!"
    assert load(os.path.join(ref_layout.metadata(), "logs", "src.log")) == "srclog!!"

    pref = c.get_latest_package_reference(ref)
    pref_layout = c.get_latest_pkg_layout(pref)
    assert os.listdir(pref_layout.metadata()) == ["logs"]
    assert os.listdir(os.path.join(pref_layout.metadata(), "logs")) == ["mylogs.txt"]
    assert load(os.path.join(pref_layout.metadata(), "logs", "mylogs.txt")) == "some logs!!!"

    # Now upload everything
    c.run("upload * -c -r=default")
    assert "metadata/logs/file.log" in c.out
    assert "metadata/logs/src.log" in c.out
    assert "metadata/logs/mylogs.txt" in c.out

    c.run("remove * -c")
    c.run("install --requires=pkg/0.1")  # wont install metadata by default
    assert not os.path.exists(ref_layout.metadata())
    assert not os.path.exists(pref_layout.metadata())

    c.run("remove * -c")
    save(c.cache.new_config_path, "core.metadata:download=['logs']")
    c.run("install --requires=pkg/0.1")
    assert load(os.path.join(ref_layout.metadata(), "logs", "file.log")) == "log contents!"
    assert load(os.path.join(ref_layout.metadata(), "logs", "src.log")) == "srclog!!"
    assert load(os.path.join(pref_layout.metadata(), "logs", "mylogs.txt")) == "some logs!!!"


def test_metadata_logs_local():
    c = TestClient()
    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import save, copy

        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"

            def layout(self):
                self.folders.build = "mybuild"
                self.folders.generators = "mybuild/generators"

            def export(self):
                copy(self, "*.log", src=self.recipe_folder,
                     dst=os.path.join(self.recipe_metadata_folder, "logs"))

            def source(self):
                save(self, os.path.join(self.recipe_metadata_folder, "logs", "src.log"), "srclog!!")

            def build(self):
                save(self, "mylogs.txt", "some logs!!!")
                copy(self, "mylogs.txt", src=self.build_folder,
                     dst=os.path.join(self.pkg_metadata_folder, "logs"))
        """)
    c.save({"conanfile.py": conanfile,
            "file.log": "log contents!"})

    c.run("source .")
    assert c.load("metadata/logs/src.log") == "srclog!!"
    c.run("build .")
    assert c.load("mybuild/metadata/logs/mylogs.txt") == "some logs!!!"


@pytest.mark.skip(reason="just wip")
def test_sources_backup():
    c = TestClient(default_server_user=True)
    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import save, download, copy

        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"

            def source(self):
                # Local "conan source"? use "conan metadata get pkg/0.1 srcs"?
                self._conan_helpers.remote_manager.get_recipe_metadata(self.ref, "srcs")
                download(self, "url")
                save(self, os.path.join(self.recipe_metadata_folder, "srcs", "src.log"), "srclog!!")
        """)
    c.save({"conanfile.py": conanfile})
    c.run("create .")
