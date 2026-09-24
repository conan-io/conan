import os
import pytest

from conan.internal.paths import CONAN_METADATA_SUBFOLDER
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient
from conan.internal.util.files import save, load


class TestConanMetadataSubfolder:

    @pytest.fixture()
    def uploaded_pkg(self):
        """Create and upload pkg/0.1 with metadata/.conan/info.txt, no --metadata flag."""
        c = TestClient(default_server_user=True, light=True)
        c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
        c.run("create .")
        c.run("cache path pkg/0.1 --folder=metadata")
        metadata_path = str(c.stdout).strip()
        save(os.path.join(metadata_path, CONAN_METADATA_SUBFOLDER, "info.txt"), "conan metadata content")
        c.run("upload * -c -r=default")
        return c

    def test_create_upload_install(self, uploaded_pkg):
        """metadata/.conan is always uploaded with recipe and always downloaded on install."""
        c2 = TestClient(servers=uploaded_pkg.servers, light=True)
        c2.run("install --requires=pkg/0.1")
        c2.run("cache path pkg/0.1 --folder=metadata")
        metadata_path = str(c2.stdout).strip()
        assert load(os.path.join(metadata_path, CONAN_METADATA_SUBFOLDER, "info.txt")) == "conan metadata content"

    def test_download_irrespective_of_metadata_filter(self, uploaded_pkg):
        """conan download always gets metadata/.conan regardless of --metadata filter."""
        c2 = TestClient(servers=uploaded_pkg.servers, light=True)

        # Without --metadata flag: .conan subfolder is still fetched
        c2.run("download pkg/0.1 -r=default")
        c2.run("cache path pkg/0.1 --folder=metadata")
        metadata_path = str(c2.stdout).strip()
        assert load(os.path.join(metadata_path, CONAN_METADATA_SUBFOLDER, "info.txt")) == "conan metadata content"

        c2.run("remove * -c")

        # With --metadata filtering other patterns: .conan subfolder still fetched
        c2.run("download pkg/0.1 -r=default --metadata=other/*")
        c2.run("cache path pkg/0.1 --folder=metadata")
        metadata_path = str(c2.stdout).strip()
        assert load(os.path.join(metadata_path, CONAN_METADATA_SUBFOLDER, "info.txt")) == "conan metadata content"

    def test_update_conan_metadata_already_in_server(self):
        """metadata/.conan is re-uploaded even when the recipe revision already exists in server.

        Scenario: first upload has no .conan files; later .conan files are written and a
        second upload should send them so that other clients receive the updated data.
        """
        c = TestClient(default_server_user=True, light=True)
        c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
        c.run("create .")

        # First upload: no .conan/ files yet
        c.run("upload * -c -r=default")
        c.run("cache path pkg/0.1 --folder=metadata")
        metadata_path = str(c.stdout).strip()

        # Write .conan/ data AFTER the initial upload (recipe revision unchanged)
        save(os.path.join(metadata_path, CONAN_METADATA_SUBFOLDER, "generated.h"), "// v1")

        # Second upload: recipe revision already on server, but .conan/ data is new
        c.run("upload * -c -r=default")

        # Fresh client must receive the .conan/ file
        c2 = TestClient(servers=c.servers, light=True)
        c2.run("install --requires=pkg/0.1")
        c2.run("cache path pkg/0.1 --folder=metadata")
        metadata_path2 = str(c2.stdout).strip()
        assert load(os.path.join(metadata_path2, CONAN_METADATA_SUBFOLDER, "generated.h")) == "// v1"

    def test_update_existing_conan_metadata_already_in_server(self):
        """Updating metadata/.conan content after initial upload is propagated to clients.

        Scenario: first upload includes .conan files; those files are later modified and
        re-uploaded (recipe revision still the same); a third client must see the new content.
        """
        c1 = TestClient(default_server_user=True, light=True)
        c1.save({"conanfile.py": GenConanfile("pkg", "0.1")})
        c1.run("create .")
        c1.run("cache path pkg/0.1 --folder=metadata")
        metadata_path1 = str(c1.stdout).strip()
        save(os.path.join(metadata_path1, CONAN_METADATA_SUBFOLDER, "generated.h"), "// v1")
        c1.run("upload * -c -r=default")

        # Second client installs and gets v1
        c2 = TestClient(servers=c1.servers, inputs=["admin", "password"], light=True)
        c2.run("install --requires=pkg/0.1")
        c2.run("cache path pkg/0.1 --folder=metadata")
        metadata_path2 = str(c2.stdout).strip()
        assert load(os.path.join(metadata_path2, CONAN_METADATA_SUBFOLDER, "generated.h")) == "// v1"

        # c2 updates the .conan/ file and re-uploads (recipe revision still unchanged)
        save(os.path.join(metadata_path2, CONAN_METADATA_SUBFOLDER, "generated.h"), "// v2")
        c2.run("upload * -c -r=default")

        # Third client must see v2
        c3 = TestClient(servers=c1.servers, inputs=["admin", "password"], light=True)
        c3.run("install --requires=pkg/0.1")
        c3.run("cache path pkg/0.1 --folder=metadata")
        metadata_path3 = str(c3.stdout).strip()
        assert load(os.path.join(metadata_path3, CONAN_METADATA_SUBFOLDER, "generated.h")) == "// v2"

    def test_conan_metadata_tied_to_recipe_revision(self):
        """metadata/.conan/ is only fetched when the recipe revision itself is fetched, or
        when explicitly re-synced; a plain ``install``/``download`` never refreshes it.

        Scenario from the review of https://github.com/conan-io/conan/pull/20114:
        - client1 uploads mylib/0.1 with metadata/.conan/time.txt == "t1"
        - client2, with a clean cache, installs it and gets "t1"
        - client1 updates the file to "t2" and re-uploads, without creating a new revision
        - client2 does NOT get "t2" with a plain ``install`` or ``download``, because the
          recipe revision it has cached is already the latest one, so nothing is downloaded.
          (``--update`` does refresh it, see ``test_update_refreshes_conan_metadata``)

        To explicitly re-sync the metadata of an already cached revision, ``conan download``
        with a ``--metadata`` pattern can also be used.
        """
        c1 = TestClient(default_server_user=True, light=True)
        c1.save({"conanfile.py": GenConanfile("mylib", "0.1")})
        c1.run("create .")
        c1.run("cache path mylib/0.1 --folder=metadata")
        metadata_path1 = str(c1.stdout).strip()
        time_txt1 = os.path.join(metadata_path1, CONAN_METADATA_SUBFOLDER, "time.txt")
        save(time_txt1, "t1")
        c1.run("upload * -c -r=default")

        # client2 with a clean cache gets the metadata of that revision
        c2 = TestClient(servers=c1.servers, inputs=["admin", "password"], light=True)
        c2.run("install --requires=mylib/0.1")
        c2.run("cache path mylib/0.1 --folder=metadata")
        metadata_path2 = str(c2.stdout).strip()
        time_txt2 = os.path.join(metadata_path2, CONAN_METADATA_SUBFOLDER, "time.txt")
        assert load(time_txt2) == "t1"

        # client1 updates the metadata and re-uploads it, the recipe revision is the same
        save(time_txt1, "t2")
        c1.run("upload * -c -r=default")

        # client2 keeps "t1", the cached revision is unchanged, nothing is re-downloaded
        c2.run("install --requires=mylib/0.1")
        assert load(time_txt2) == "t1"
        # same for a plain ``download``, that only completes the missing artifacts
        c2.run("download mylib/0.1 -r=default")
        assert load(time_txt2) == "t1"

        # Explicitly asking for the metadata does re-sync it
        c2.run("download mylib/0.1 -r=default --metadata=*")
        assert load(time_txt2) == "t2"

        # And a fresh cache also gets the new contents of the same revision
        c3 = TestClient(servers=c1.servers, inputs=["admin", "password"], light=True)
        c3.run("install --requires=mylib/0.1")
        c3.run("cache path mylib/0.1 --folder=metadata")
        metadata_path3 = str(c3.stdout).strip()
        assert load(os.path.join(metadata_path3, CONAN_METADATA_SUBFOLDER, "time.txt")) == "t2"

    def test_no_download_cached(self):
        """metadata/.conan/ is never stored in the "core.download:download_cache".

        Same rationale as the regular metadata: it can be re-uploaded for an existing revision,
        so the same url can return different contents and it cannot be cached by url.
        """
        c1 = TestClient(default_server_user=True, light=True)
        c1.save({"conanfile.py": GenConanfile("mylib", "0.1")})
        c1.run("create .")
        c1.run("cache path mylib/0.1 --folder=metadata")
        metadata_path1 = str(c1.stdout).strip()
        time_txt1 = os.path.join(metadata_path1, CONAN_METADATA_SUBFOLDER, "time.txt")
        save(time_txt1, "t1")
        c1.run("upload * -c -r=default")

        c2 = TestClient(servers=c1.servers, inputs=["admin", "password"], light=True)
        # MOST important part: activate the download cache
        c2.save_home({"global.conf": f"core.download:download_cache={temp_folder()}\n"})
        c2.run("install --requires=mylib/0.1")
        c2.run("cache path mylib/0.1 --folder=metadata")
        metadata_path2 = str(c2.stdout).strip()
        time_txt2 = os.path.join(metadata_path2, CONAN_METADATA_SUBFOLDER, "time.txt")
        assert load(time_txt2) == "t1"

        # client1 updates the metadata of the same revision
        save(time_txt1, "t2")
        c1.run("upload * -c -r=default")

        # The new contents are downloaded, not served from the download cache
        c2.run("remove * -c")
        c2.run("install --requires=mylib/0.1")
        assert load(time_txt2) == "t2"

    def test_update_refreshes_conan_metadata(self):
        """``--update`` re-fetches metadata/.conan/ for an already cached recipe revision,
        as long as some of it was already present locally (see
        ``test_update_skips_refresh_of_never_downloaded_metadata`` for the opposite case).
        """
        c = TestClient(default_server_user=True, light=True)
        c.save({"conanfile.py": GenConanfile("mylib", "0.1")})
        c.run("create .")
        c.run("cache path mylib/0.1 --folder=metadata")
        metadata_path = str(c.stdout).strip()
        save(os.path.join(metadata_path, CONAN_METADATA_SUBFOLDER, "time.txt"), "t1")
        c.run("upload * -c -r=default")

        c2 = TestClient(servers=c.servers, inputs=["admin", "password"], light=True)
        c2.run("install --requires=mylib/0.1")
        c2.run("cache path mylib/0.1 --folder=metadata")
        metadata_path2 = str(c2.stdout).strip()
        assert load(os.path.join(metadata_path2, CONAN_METADATA_SUBFOLDER, "time.txt")) == "t1"

        # Update the private metadata on c and re-upload (same recipe revision)
        save(os.path.join(metadata_path, CONAN_METADATA_SUBFOLDER, "time.txt"), "t2")
        c.run("upload * -c -r=default")

        # Without --update: c2 keeps the cached t1
        c2.run("install --requires=mylib/0.1")
        assert load(os.path.join(metadata_path2, CONAN_METADATA_SUBFOLDER, "time.txt")) == "t1"

        # With --update: c2 gets the refreshed t2 from the server, because it already had
        # some metadata/.conan content locally (from the initial install above)
        c2.run("install --requires=mylib/0.1 --update")
        assert load(os.path.join(metadata_path2, CONAN_METADATA_SUBFOLDER, "time.txt")) == "t2"

        # A fresh download will get the new metadata.
        # If the recipe doesn't update, the metadata doesn't update
        c2.run("remove * -c")
        c2.run("install --requires=mylib/0.1")
        assert load(os.path.join(metadata_path2, CONAN_METADATA_SUBFOLDER, "time.txt")) == "t2"

    def test_update_skips_refresh_of_never_downloaded_metadata(self):
        """``--update`` does NOT trigger an extra remote check for metadata/.conan/ when the
        local recipe revision never had any of it downloaded in the first place. This avoids
        paying that extra cost on every ``--update`` for the (common) case of a reference that
        doesn't use this private metadata at all.

        Scenario:
        - pkg/0.1 is first uploaded with no metadata/.conan/ content whatsoever
        - a client installs it: its local metadata/.conan/ folder doesn't even exist
        - metadata/.conan/info.txt is added on the *same* recipe revision and re-uploaded
        - ``--update`` still does NOT pick it up, because there was nothing locally to refresh
        - only a fresh install (clean cache) gets it, same as an explicit ``--metadata`` download
        """
        c = TestClient(default_server_user=True, light=True)
        c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
        c.run("create .")
        c.run("upload * -c -r=default")  # no metadata/.conan/ content yet

        c2 = TestClient(servers=c.servers, inputs=["admin", "password"], light=True)
        c2.run("install --requires=pkg/0.1")
        c2.run("cache path pkg/0.1 --folder=metadata")
        metadata_path2 = str(c2.stdout).strip()
        conan_metadata2 = os.path.join(metadata_path2, CONAN_METADATA_SUBFOLDER)
        assert not os.path.isdir(conan_metadata2) or not os.listdir(conan_metadata2)

        # metadata/.conan/ content appears on the server for that same revision
        c.run("cache path pkg/0.1 --folder=metadata")
        metadata_path = str(c.stdout).strip()
        save(os.path.join(metadata_path, CONAN_METADATA_SUBFOLDER, "info.txt"),
             "conan metadata content")
        c.run("upload * -c -r=default")

        # --update doesn't fetch it: the local folder was empty, no refresh is attempted
        c2.run("install --requires=pkg/0.1 --update")
        assert not os.path.isdir(conan_metadata2) or not os.listdir(conan_metadata2)

        # A fresh install (clean cache) does get it
        # c2.run("download pkg/0.1 --only-recipe -r=default") does NOT work, skips download
        c2.run("remove * -c")
        c2.run("install --requires=pkg/0.1")
        c2.run("cache path pkg/0.1 --folder=metadata")
        metadata_path2 = str(c2.stdout).strip()
        assert load(os.path.join(metadata_path2, CONAN_METADATA_SUBFOLDER, "info.txt")) == \
            "conan metadata content"
