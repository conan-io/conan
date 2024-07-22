import os
import shutil
import textwrap

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient
from conans.util.files import save


class TestMetadataTestPackage:
    """ It is possible to store the test_package itself in the recipe metadata and recover it
    later to execute it
    """

    def test_round_trip_with_hook(self):
        c = TestClient(default_server_user=True)
        # TODO: Better strategy for storing clean test_package, zipping it, etc
        my_hook = textwrap.dedent("""\
            import os
            from conan.tools.files import copy

            def post_export(conanfile):
               conanfile.output.info("Storing test_package")
               folder = os.path.join(conanfile.recipe_folder, "test_package")
               copy(conanfile, "*", src=folder,
                    dst=os.path.join(conanfile.recipe_metadata_folder, "test_package"))
            """)
        hook_path = os.path.join(c.cache.hooks_path, "my_hook", "hook_my_hook.py")
        save(hook_path, my_hook)
        c.save({"conanfile.py": GenConanfile("pkg", "0.1"),
                "test_package/conanfile.py": GenConanfile().with_test("pass")})
        c.run("create .")
        assert "Testing the package" in c.out

        # Now upload and remove everything
        c.run("upload * -c -r=default")
        assert "pkg/0.1: Recipe metadata: 1 files" in c.out
        c.run("remove * -c")

        c.run("install --requires=pkg/0.1 -r=default")
        # Recovery of the test package
        # TODO: Discuss if we want better UX, in a single step or something like that
        # Forcing the download of the metadata of cache-existing things with the "download" command
        c.run("download pkg/0.1 -r=default --metadata=test_package*")
        c.run("cache path pkg/0.1 --folder=metadata")
        metadata_path = str(c.stdout).strip()
        shutil.copytree(metadata_path, os.path.join(c.current_folder, "metadata"))

        # Execute the test_package
        c.run("test metadata/test_package pkg/0.1")
        assert "pkg/0.1 (test package): Running test()" in c.out
