import os
import pytest

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
        save(os.path.join(metadata_path, ".conan", "info.txt"), "conan metadata content")
        c.run("upload * -c -r=default")
        return c

    def test_create_upload_install(self, uploaded_pkg):
        """metadata/.conan is always uploaded with recipe and always downloaded on install."""
        c2 = TestClient(servers=uploaded_pkg.servers, light=True)
        c2.run("install --requires=pkg/0.1")
        c2.run("cache path pkg/0.1 --folder=metadata")
        metadata_path = str(c2.stdout).strip()
        assert load(os.path.join(metadata_path, ".conan", "info.txt")) == "conan metadata content"

    def test_download_irrespective_of_metadata_filter(self, uploaded_pkg):
        """conan download always gets metadata/.conan regardless of --metadata filter."""
        c2 = TestClient(servers=uploaded_pkg.servers, light=True)

        # Without --metadata flag: .conan is still fetched
        c2.run("download pkg/0.1 -r=default")
        c2.run("cache path pkg/0.1 --folder=metadata")
        metadata_path = str(c2.stdout).strip()
        assert load(os.path.join(metadata_path, ".conan", "info.txt")) == "conan metadata content"

        c2.run("remove * -c")

        # With --metadata filtering other patterns: .conan subfolder still fetched
        c2.run("download pkg/0.1 -r=default --metadata=other/*")
        c2.run("cache path pkg/0.1 --folder=metadata")
        metadata_path = str(c2.stdout).strip()
        assert load(os.path.join(metadata_path, ".conan", "info.txt")) == "conan metadata content"
