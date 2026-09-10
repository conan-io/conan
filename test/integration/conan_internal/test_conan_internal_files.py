import os

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient
from conan.internal.util.files import save, load
from conan.internal.cache.conan_reference_layout import CONAN_INTERNAL_FOLDER


class TestConanInternalFiles:

    def test_upload_download_roundtrip(self):
        """Full round-trip:
        1. Create recipe, write internal file, upload.
        2. Install in fresh client, verify internal file downloaded (not in manifest).
        3. Update internal file, re-upload.
        4. Install in third client, verify updated file is present.
        """
        c1 = TestClient(default_server_user=True, light=True)
        c1.save({"conanfile.py": GenConanfile("pkg", "0.1")})
        c1.run("create .")

        # Write an internal file into ci/ for the recipe
        layout1 = c1.exported_layout()
        internal_folder1 = layout1.conan_internal()
        os.makedirs(internal_folder1, exist_ok=True)
        save(os.path.join(internal_folder1, "data.json"), '{"version": 1}')

        # Upload — internal file travels with recipe, no extra flag
        c1.run("upload pkg/0.1 -c -r=default")

        # Install in a clean second client
        c2 = TestClient(servers=c1.servers, inputs=["admin", "password"], light=True)
        c2.run("install --requires=pkg/0.1")

        # Internal file must be present in ci/
        layout2 = c2.get_latest_ref_layout("pkg/0.1")
        downloaded_file = os.path.join(layout2.conan_internal(), "data.json")
        assert os.path.isfile(downloaded_file)
        assert load(downloaded_file) == '{"version": 1}'

        # Internal file must NOT appear in conanmanifest.txt
        manifest_content = load(os.path.join(layout2.export(), "conanmanifest.txt"))
        assert "data.json" not in manifest_content
        assert CONAN_INTERNAL_FOLDER not in manifest_content

        # Update the internal file in c2 and re-upload
        save(downloaded_file, '{"version": 2}')
        c2.run("upload pkg/0.1 -c -r=default")

        # Third client installs and sees the updated internal file
        c3 = TestClient(servers=c1.servers, inputs=["admin", "password"], light=True)
        c3.run("install --requires=pkg/0.1")
        layout3 = c3.get_latest_ref_layout("pkg/0.1")
        updated_file = os.path.join(layout3.conan_internal(), "data.json")
        assert os.path.isfile(updated_file)
        assert load(updated_file) == '{"version": 2}'
