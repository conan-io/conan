import os
import textwrap

from conan.test.utils.tools import TestClient
from conan.internal.util.files import load


class TestRecipeInternalFolderCodegen:
    """Emulates the issue #20118 use case: a recipe runs codegen in generate() that is
    slow and profile-independent. Results are cached in recipe_internal_folder so that
    subsequent builds (different profiles) skip the generation entirely."""

    def test_codegen_roundtrip(self):
        # A recipe whose generate() writes a "generated" file from its sources.
        # The first call runs the (simulated) codegen; subsequent calls reuse the cache.
        conanfile = textwrap.dedent("""\
            import os
            from conan import ConanFile
            from conan.tools.files import copy, save, load

            class MyIDLLib(ConanFile):
                name = "myidl"
                version = "0.1"
                exports = "schema.idl"

                def generate(self):
                    cache_dir = self.recipe_internal_folder
                    generated_h = os.path.join(cache_dir, "generated.h")

                    if not os.path.isfile(generated_h):
                        self.output.info("Running codegen (first time)")
                        idl = load(self, os.path.join(self.recipe_folder, "schema.idl"))
                        save(self, generated_h, f"// generated from: {idl.strip()}")
                    else:
                        self.output.info("Reusing cached generated files")

                    copy(self, "generated.h", cache_dir, self.build_folder)
        """)

        c = TestClient(default_server_user=True, light=True)
        c.save({"conanfile.py": conanfile, "schema.idl": "struct Foo { int x; };"})
        c.run("export .")

        # --- First install (profile A) ---
        c.run("install --requires=myidl/0.1 --build=myidl/0.1")
        assert "Running codegen (first time)" in c.out

        layout = c.get_latest_ref_layout("myidl/0.1")
        cached_h = os.path.join(layout.conan_internal(), "generated.h")
        assert os.path.isfile(cached_h)
        assert "struct Foo" in load(cached_h)

        # --- Second install (simulates a different profile) ---
        # Cache is populated; codegen must NOT run again
        c.run("install --requires=myidl/0.1 --build=myidl/0.1")
        assert "Reusing cached generated files" in c.out
        assert "Running codegen (first time)" not in c.out

        # --- Upload and install on a fresh client ---
        c.run("upload myidl/0.1 -c -r=default")

        c2 = TestClient(servers=c.servers, inputs=["admin", "password"], light=True)
        c2.run("install --requires=myidl/0.1")

        layout2 = c2.get_latest_ref_layout("myidl/0.1")
        downloaded_h = os.path.join(layout2.conan_internal(), "generated.h")
        assert os.path.isfile(downloaded_h)
        assert "struct Foo" in load(downloaded_h)

        # On the fresh client the cache is already populated from the download,
        # so a build also skips codegen
        c2.run("install --requires=myidl/0.1 --build=myidl/0.1")
        assert "Reusing cached generated files" in c2.out
        assert "Running codegen (first time)" not in c2.out
