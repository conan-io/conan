import os
import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient, NO_SETTINGS_PACKAGE_ID
from conans.util.files import save, load


class TestMetadataCommands:

    @pytest.fixture
    def create_conan_pkg(self):
        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": GenConanfile("pkg", "0.1")})
        client.run("create .")
        pid = client.created_package_id("pkg/0.1")
        return client, pid

    def save_metadata_file(self, client, pkg_ref, filename="somefile.log"):
        client.run(f"cache path {pkg_ref} --folder=metadata")
        metadata_path = str(client.stdout).strip()
        myfile = os.path.join(metadata_path, "logs", filename)
        save(myfile, f"{pkg_ref}!!!!")
        return metadata_path, myfile

    def test_upload(self, create_conan_pkg):
        c, pid = create_conan_pkg

        # Add some metadata
        self.save_metadata_file(c, "pkg/0.1", "mylogs.txt")
        self.save_metadata_file(c, f"pkg/0.1:{pid}", "mybuildlogs.txt")
        # Now upload everything
        c.run("upload * -c -r=default")
        assert "pkg/0.1: Recipe metadata: 1 files" in c.out
        assert "pkg/0.1:da39a3ee5e6b4b0d3255bfef95601890afd80709: Package metadata: 1 files" in c.out

        # Add new files to the metadata
        self.save_metadata_file(c, "pkg/0.1", "mylogs2.txt")
        self.save_metadata_file(c, f"pkg/0.1:{pid}", "mybuildlogs2.txt")
        # Upload the metadata, even if the revisions exist in the server
        # adding the new metadata logs files
        c.run("upload * -c -r=default --metadata=*")
        assert "pkg/0.1: Recipe metadata: 2 files" in c.out
        assert "pkg/0.1:da39a3ee5e6b4b0d3255bfef95601890afd80709: Package metadata: 2 files" in c.out

        c.run("remove * -c")
        c.run("install --requires=pkg/0.1")  # wont install metadata by default
        c.run("cache path pkg/0.1 --folder=metadata", assert_error=True)
        assert "'metadata' folder does not exist for the reference pkg/0.1" in c.out
        c.run(f"cache path pkg/0.1:{pid} --folder=metadata", assert_error=True)
        assert f"'metadata' folder does not exist for the reference pkg/0.1:{pid}" in c.out

        # Forcing the download of the metadata of cache-existing things with the "download" command
        c.run("download pkg/0.1 -r=default --metadata=*")
        c.run(f"cache path pkg/0.1 --folder=metadata")
        metadata_path = str(c.stdout).strip()
        c.run(f"cache path pkg/0.1:{pid} --folder=metadata")
        pkg_metadata_path = str(c.stdout).strip()
        for f in "logs/mylogs.txt", "logs/mylogs2.txt":
            assert os.path.isfile(os.path.join(metadata_path, f))
        for f in "logs/mybuildlogs.txt", "logs/mybuildlogs2.txt":
            assert os.path.isfile(os.path.join(pkg_metadata_path, f))

    def test_update_contents(self):
        c = TestClient(default_server_user=True)
        c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
        c.run("export .")

        # Add some metadata
        _, myfile = self.save_metadata_file(c, "pkg/0.1", "mylogs.txt")

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

    def test_folder_exist(self, create_conan_pkg):
        """ so we can cp -R to the metadata folder, having to create the folder in the cache
        is weird
        """
        c, _ = create_conan_pkg
        c.run("cache path pkg/0.1 --folder=metadata")
        metadata_path = str(c.stdout).strip()
        assert os.path.isdir(metadata_path)
        c.run(f"cache path pkg/0.1:{NO_SETTINGS_PACKAGE_ID} --folder=metadata")
        pkg_metadata_path = str(c.stdout).strip()
        assert os.path.isdir(pkg_metadata_path)

    def test_direct_download_redownload(self, create_conan_pkg):
        """ When we directly download things, without "conan install" first, it is also able
        to fetch the requested metadata

        Also, re-downloading same thing shouldn't fail
        """
        c, pid = create_conan_pkg

        # Add some metadata
        metadata_path, _ = self.save_metadata_file(c, "pkg/0.1", "mylogs.txt")
        self.save_metadata_file(c, f"pkg/0.1:{pid}", "mybuildlogs.txt")

        # Now upload everything
        c.run("upload * -c -r=default")
        assert "pkg/0.1: Recipe metadata: 1 files" in c.out
        assert "pkg/0.1:da39a3ee5e6b4b0d3255bfef95601890afd80709: Package metadata: 1 files" in c.out

        c.run("remove * -c")

        # Forcing the download of the metadata of cache-existing things with the "download" command
        c.run("download pkg/0.1 -r=default --metadata=*")
        assert os.path.isfile(os.path.join(metadata_path, "logs", "mylogs.txt"))
        c.run(f"cache path pkg/0.1:{pid} --folder=metadata")
        pkg_metadata_path = str(c.stdout).strip()
        assert os.path.isfile(os.path.join(pkg_metadata_path, "logs", "mybuildlogs.txt"))

        # Re-download shouldn't fail
        c.run("download pkg/0.1 -r=default --metadata=*")
        assert os.path.isfile(os.path.join(metadata_path, "logs", "mylogs.txt"))
        c.run(f"cache path pkg/0.1:{pid} --folder=metadata")
        pkg_metadata_path = str(c.stdout).strip()
        assert os.path.isfile(os.path.join(pkg_metadata_path, "logs", "mybuildlogs.txt"))

    def test_no_download_cached(self, create_conan_pkg):
        """ as the metadata can change, no checksum, no revision, cannot be cached
        """
        c, pid = create_conan_pkg

        # Add some metadata
        _, myrecipefile = self.save_metadata_file(c, "pkg/0.1", "mylogs.txt")
        _, mypkgfile = self.save_metadata_file(c, f"pkg/0.1:{pid}", "mybuildlogs.txt")

        # Now upload everything
        c.run("upload * -c -r=default")
        assert "pkg/0.1: Recipe metadata: 1 files" in c.out
        assert "pkg/0.1:da39a3ee5e6b4b0d3255bfef95601890afd80709: Package metadata: 1 files" in c.out

        c2 = TestClient(servers=c.servers)
        tmp_folder = temp_folder()
        # MOST important part: activate cache
        save(c2.cache.new_config_path, f"core.download:download_cache={tmp_folder}\n")

        # download package and metadata
        c2.run("download pkg/0.1 -r=default --metadata=*")
        c2.run("cache path pkg/0.1 --folder=metadata")
        c2_metadata_path = str(c2.stdout).strip()
        mylogs = load(os.path.join(c2_metadata_path, "logs", "mylogs.txt"))
        assert "pkg/0.1!!!!" in mylogs
        c2.run(f"cache path pkg/0.1:{pid} --folder=metadata")
        c2_pkg_metadata_path = str(c2.stdout).strip()
        mybuildlogs = load(os.path.join(c2_pkg_metadata_path, "logs", "mybuildlogs.txt"))
        assert f"pkg/0.1:{pid}!!!!" in mybuildlogs

        # Now the other client will update the metadata
        save(myrecipefile, "mylogs2!!!!")
        save(mypkgfile, "mybuildlogs2!!!!")
        c.run("upload * -c -r=default --metadata=*")
        assert "pkg/0.1: Recipe metadata: 1 files" in c.out
        assert "pkg/0.1:da39a3ee5e6b4b0d3255bfef95601890afd80709: Package metadata: 1 files" in c.out

        # re-download of metadata in c2
        c2.run("remove * -c")  # to make sure the download cache works
        c2.run("download pkg/0.1 -r=default --metadata=*")
        mylogs = load(os.path.join(c2_metadata_path, "logs", "mylogs.txt"))
        assert "mylogs2!!!!" in mylogs
        mybuildlogs = load(os.path.join(c2_pkg_metadata_path, "logs", "mybuildlogs.txt"))
        assert "mybuildlogs2!!!!" in mybuildlogs

    def test_upload_ignored_metadata(self, create_conan_pkg):
        """
        Upload command should ignore metadata files when passing --metadata=""
        """
        client, pid = create_conan_pkg

        self.save_metadata_file(client, "pkg/0.1")
        self.save_metadata_file(client, f"pkg/0.1:{pid}")

        client.run('upload * --confirm --remote=default --metadata=""')
        assert "Recipe metadata" not in client.out
        assert "Package metadata" not in client.out

    def test_upload_ignored_metadata_with_pattern(self, create_conan_pkg):
        """
        Upload command should fail when passing --metadata="" and a pattern
        """
        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": GenConanfile("pkg", "0.1")})
        client.run("export .")

        client.run('upload * --confirm --remote=default --metadata="" --metadata="logs/*"',
                   assert_error=True)
        assert "ERROR: Empty string and patterns can not be mixed for metadata." in client.out
