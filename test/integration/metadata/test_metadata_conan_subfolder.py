import os
import pytest

from conan.internal.paths import CONAN_METADATA_SUBFOLDER
from conan.test.assets.genconanfile import GenConanfile
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

    def test_update_refreshes_conan_metadata(self):
        """install --update refreshes metadata/.conan/ even when the recipe revision is unchanged.

        The client updates the private metadata directly in the cache folder (no recipe
        hook involved) and re-uploads. A second client that already has the recipe cached
        must pick up the new content only after ``--update``.
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

        # With --update: c2 gets the refreshed t2 from the server
        c2.run("install --requires=mylib/0.1 --update")
        assert load(os.path.join(metadata_path2, CONAN_METADATA_SUBFOLDER, "time.txt")) == "t2"
