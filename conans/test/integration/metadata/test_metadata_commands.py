import os

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient
from conans.util.files import save


class TestMetadataCommands:

    def test_upload(self):
        c = TestClient(default_server_user=True)
        c.save({"conanfile.py": GenConanfile("pkg", "0.1"),
                "myfile": "mycontent",
                "folder/other": "other content"})
        c.run("create .")
        pid = c.created_package_id("pkg/0.1")

        # Add some metadata
        c.run("cache path pkg/0.1 --folder=metadata")
        metadata_path = str(c.stdout).strip()
        myfile = os.path.join(metadata_path, "logs", "mylogs.txt")
        save(myfile, "mylogs!!!!")

        c.run(f"cache path pkg/0.1:{pid} --folder=metadata")
        pkg_metadata_path = str(c.stdout).strip()
        myfile = os.path.join(pkg_metadata_path, "logs", "mybuildlogs.txt")
        save(myfile, "mybuildlogs!!!!")

        # Now upload everything
        c.run("upload * -c -r=default")
        assert "metadata/logs/mylogs.txt" in c.out
        assert "metadata/logs/mybuildlogs.txt" in c.out

        c.run("remove * -c")
        c.run("install --requires=pkg/0.1")  # wont install metadata by default
        c.run("cache path pkg/0.1 --folder=metadata")
        assert not os.path.exists(metadata_path)
        assert not os.path.exists(pkg_metadata_path)

        """c.run("remove * -c")
        save(c.cache.new_config_path, "core.metadata:download=['logs']")
        c.run("install --requires=pkg/0.1")
        assert load(os.path.join(ref_layout.metadata(), "logs", "file.log")) == "log contents!"
        assert load(os.path.join(ref_layout.metadata(), "logs", "src.log")) == "srclog!!"
        assert load(os.path.join(pref_layout.metadata(), "logs", "mylogs.txt")) == "some logs!!!"
"""
