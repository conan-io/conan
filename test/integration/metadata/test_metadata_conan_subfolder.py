import os
import textwrap
import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient
from conan.internal.util.files import save, load


class TestConanMetadataSubfolder:

    @pytest.fixture()
    def uploaded_pkg(self):
        """Create and upload pkg/0.1 with metadata/conan/info.txt, no --metadata flag."""
        c = TestClient(default_server_user=True, light=True)
        c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
        c.run("create .")
        c.run("cache path pkg/0.1 --folder=metadata")
        metadata_path = str(c.stdout).strip()
        save(os.path.join(metadata_path, "conan", "info.txt"), "conan metadata content")
        c.run("upload * -c -r=default")
        return c

    def test_create_upload_install(self, uploaded_pkg):
        """metadata/conan is always uploaded with recipe and always downloaded on install."""
        c2 = TestClient(servers=uploaded_pkg.servers, light=True)
        c2.run("install --requires=pkg/0.1")
        c2.run("cache path pkg/0.1 --folder=metadata")
        metadata_path = str(c2.stdout).strip()
        assert load(os.path.join(metadata_path, "conan", "info.txt")) == "conan metadata content"

    def test_download_irrespective_of_metadata_filter(self, uploaded_pkg):
        """conan download always gets metadata/conan regardless of --metadata filter."""
        c2 = TestClient(servers=uploaded_pkg.servers, light=True)

        # Without --metadata flag: conan subfolder is still fetched
        c2.run("download pkg/0.1 -r=default")
        c2.run("cache path pkg/0.1 --folder=metadata")
        metadata_path = str(c2.stdout).strip()
        assert load(os.path.join(metadata_path, "conan", "info.txt")) == "conan metadata content"

        c2.run("remove * -c")

        # With --metadata filtering other patterns: conan subfolder still fetched
        c2.run("download pkg/0.1 -r=default --metadata=other/*")
        c2.run("cache path pkg/0.1 --folder=metadata")
        metadata_path = str(c2.stdout).strip()
        assert load(os.path.join(metadata_path, "conan", "info.txt")) == "conan metadata content"

    def test_update_conan_metadata_already_in_server(self):
        """metadata/conan is re-uploaded even when the recipe revision already exists in server.

        Scenario: first upload has no conan files; later conan files are written and a
        second upload should send them so that other clients receive the updated data.
        """
        c = TestClient(default_server_user=True, light=True)
        c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
        c.run("create .")

        # First upload: no conan/ files yet
        c.run("upload * -c -r=default")
        c.run("cache path pkg/0.1 --folder=metadata")
        metadata_path = str(c.stdout).strip()

        # Write conan/ data AFTER the initial upload (recipe revision unchanged)
        save(os.path.join(metadata_path, "conan", "generated.h"), "// v1")

        # Second upload: recipe revision already on server, but conan/ data is new
        c.run("upload * -c -r=default")

        # Fresh client must receive the conan/ file
        c2 = TestClient(servers=c.servers, light=True)
        c2.run("install --requires=pkg/0.1")
        c2.run("cache path pkg/0.1 --folder=metadata")
        metadata_path2 = str(c2.stdout).strip()
        assert load(os.path.join(metadata_path2, "conan", "generated.h")) == "// v1"

    def test_update_existing_conan_metadata_already_in_server(self):
        """Updating metadata/conan content after initial upload is propagated to clients.

        Scenario: first upload includes conan/ files; those files are later modified and
        re-uploaded (recipe revision still the same); a third client must see the new content.
        """
        c1 = TestClient(default_server_user=True, light=True)
        c1.save({"conanfile.py": GenConanfile("pkg", "0.1")})
        c1.run("create .")
        c1.run("cache path pkg/0.1 --folder=metadata")
        metadata_path1 = str(c1.stdout).strip()
        save(os.path.join(metadata_path1, "conan", "generated.h"), "// v1")
        c1.run("upload * -c -r=default")

        # Second client installs and gets v1
        c2 = TestClient(servers=c1.servers, inputs=["admin", "password"], light=True)
        c2.run("install --requires=pkg/0.1")
        c2.run("cache path pkg/0.1 --folder=metadata")
        metadata_path2 = str(c2.stdout).strip()
        assert load(os.path.join(metadata_path2, "conan", "generated.h")) == "// v1"

        # c2 updates the conan/ file and re-uploads (recipe revision still unchanged)
        save(os.path.join(metadata_path2, "conan", "generated.h"), "// v2")
        c2.run("upload * -c -r=default")

        # Third client must see v2
        c3 = TestClient(servers=c1.servers, inputs=["admin", "password"], light=True)
        c3.run("install --requires=pkg/0.1")
        c3.run("cache path pkg/0.1 --folder=metadata")
        metadata_path3 = str(c3.stdout).strip()
        assert load(os.path.join(metadata_path3, "conan", "generated.h")) == "// v2"

    def test_recipe_metadata_conan_folder_accessor(self):
        """recipe_metadata_conan_folder property points to metadata/conan and is usable
        in generate() for codegen caching (issue #20118 use case)."""
        conanfile = textwrap.dedent("""\
            import os
            from conan import ConanFile
            from conan.tools.files import copy, save, load

            class MyLib(ConanFile):
                name = "mylib"
                version = "0.1"

                def generate(self):
                    conan_dir = self.recipe_metadata_conan_folder
                    generated = os.path.join(conan_dir, "generated.h")
                    if not os.path.isfile(generated):
                        self.output.info("Running codegen")
                        save(self, generated, "// generated")
                    else:
                        self.output.info("Reusing cached generated files")
                    copy(self, "generated.h", conan_dir, self.build_folder)
        """)
        c = TestClient(default_server_user=True, light=True)
        c.save({"conanfile.py": conanfile})
        c.run("install --requires=mylib/0.1 --build=mylib/0.1 --name=mylib --version=0.1"
              " --build-require" if False else "")
        c.run("export .")

        c.run("install --requires=mylib/0.1 --build=mylib/0.1")
        assert "Running codegen" in c.out

        # Second build: conan/ is populated, codegen must be skipped
        c.run("install --requires=mylib/0.1 --build=mylib/0.1")
        assert "Reusing cached generated files" in c.out

        # Upload carries the conan/ folder; fresh client skips codegen on build
        c.run("upload mylib/0.1 -c -r=default")
        c2 = TestClient(servers=c.servers, inputs=["admin", "password"], light=True)
        c2.run("install --requires=mylib/0.1 --build=mylib/0.1")
        assert "Reusing cached generated files" in c2.out
