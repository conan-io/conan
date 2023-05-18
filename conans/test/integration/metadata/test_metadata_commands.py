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

        # Add new files to the metadata
        myfile = os.path.join(metadata_path, "logs", "mylogs2.txt")
        save(myfile, "mylogs2!!!!")
        myfile = os.path.join(pkg_metadata_path, "logs", "mybuildlogs2.txt")
        save(myfile, "mybuildlogs2!!!!")
        # Upload the metadata, even if the revisions exist in the server
        # adding the new metadata logs files
        c.run("upload * -c -r=default --metadata=*")
        assert "metadata/logs/mylogs.txt" in c.out
        assert "metadata/logs/mybuildlogs.txt" in c.out
        assert "metadata/logs/mylogs2.txt" in c.out
        assert "metadata/logs/mybuildlogs2.txt" in c.out

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

        """# Regular install can also fetch metadata
        c.run("remove * -c")  # If done cleanly, not incrementally
        assert not os.path.exists(metadata_path)
        assert not os.path.exists(pkg_metadata_path)
        c.run("install --requires=pkg/0.1 --metadata=*")
        for f in "logs/mylogs.txt", "logs/mylogs2.txt":
            assert os.path.isfile(os.path.join(metadata_path, f))
        for f in "logs/mybuildlogs.txt", "logs/mybuildlogs2.txt":
            assert os.path.isfile(os.path.join(pkg_metadata_path, f))
        """
