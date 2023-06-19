import os

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient
from conans.util.files import save, load


class TestMetadataCommands:

    def test_upload(self):
        c = TestClient(default_server_user=True)
        c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
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
        assert "pkg/0.1: Recipe metadata: 1 files" in c.out
        assert "pkg/0.1:da39a3ee5e6b4b0d3255bfef95601890afd80709: Package metadata: 1 files" in c.out

        # Add new files to the metadata
        myfile = os.path.join(metadata_path, "logs", "mylogs2.txt")
        save(myfile, "mylogs2!!!!")
        myfile = os.path.join(pkg_metadata_path, "logs", "mybuildlogs2.txt")
        save(myfile, "mybuildlogs2!!!!")
        # Upload the metadata, even if the revisions exist in the server
        # adding the new metadata logs files
        c.run("upload * -c -r=default --metadata=*")
        assert "pkg/0.1: Recipe metadata: 2 files" in c.out
        assert "pkg/0.1:da39a3ee5e6b4b0d3255bfef95601890afd80709: Package metadata: 2 files" in c.out

        c.run("remove * -c")
        c.run("install --requires=pkg/0.1")  # wont install metadata by default
        c.run("cache path pkg/0.1 --folder=metadata")
        metadata_path = str(c.stdout).strip()
        c.run(f"cache path pkg/0.1:{pid} --folder=metadata")
        pkg_metadata_path = str(c.stdout).strip()
        assert not os.path.exists(metadata_path)
        assert not os.path.exists(pkg_metadata_path)

        # Forcing the download of the metadata of cache-existing things with the "download" command
        c.run("download pkg/0.1 -r=default --metadata=*")
        for f in "logs/mylogs.txt", "logs/mylogs2.txt":
            assert os.path.isfile(os.path.join(metadata_path, f))
        for f in "logs/mybuildlogs.txt", "logs/mybuildlogs2.txt":
            assert os.path.isfile(os.path.join(pkg_metadata_path, f))

    def test_update_contents(self):
        c = TestClient(default_server_user=True)
        c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
        c.run("export .")

        # Add some metadata
        c.run("cache path pkg/0.1 --folder=metadata")
        metadata_path = str(c.stdout).strip()
        myfile = os.path.join(metadata_path, "logs", "mylogs.txt")
        save(myfile, "mylogs!!!!")

        # Now upload everything
        c.run("upload * -c -r=default")
        assert "pkg/0.1: Recipe metadata: 1 files" in c.out

        # Update the metadata
        save(myfile, "mylogs2!!!!")
        # Upload the metadata, even if the revisions exist in the server
        # adding the new metadata logs files
        c.run("upload * -c -r=default --metadata=*")
        assert "pkg/0.1: Recipe metadata: 1 files" in c.out

        c.run("remove * -c")
        c.run("download pkg/0.1 -r=default --metadata=*")
        c.run("cache path pkg/0.1 --folder=metadata")
        metadata_path = str(c.stdout).strip()

        content = load(os.path.join(metadata_path, "logs", "mylogs.txt"))
        assert "mylogs2!!!!" in content
