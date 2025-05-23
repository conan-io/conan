import os
import textwrap

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def test_compression_plugin_not_valid():
    """Test an error is raised if the compression plugin is not valid"""

    c = TestClient()
    compression_plugin = textwrap.dedent(
        """
        def tar_compress(files, name, dest_dir, compresslevel=None, ref=None, recursive=False):
            return None
    """
    )

    c.save(
        {
            os.path.join(
                c.cache_folder, "extensions", "plugins", "compression.py"
            ): compression_plugin,
            "conanfile.py": GenConanfile("pkg", "1.0"),
        }
    )
    c.run("create .")
    c.run("cache save 'pkg/*'", assert_error=True)
    assert (
        "ERROR: The 'compression.py' plugin does not contain required `tar_extract` or `tar_compress` functions"
        in c.out
    )


def test_compression_plugin_correctly_load():
    """Test that the compression plugin is correctly loaded and used on:
    - cache save/restore
    - remote upload/download
    """
    c = TestClient(default_server_user=True)

    compression_plugin = textwrap.dedent(
        """
        import os
        import tarfile
        from conan.api.output import ConanOutput

        # xz compression
        def tar_compress(files, name, dest_dir, compresslevel=None, ref=None, recursive=False, *args, **kwargs):
            tgz_path = os.path.join(dest_dir, name)
            ConanOutput(scope=str(ref) if ref else "").info(f"Compressing {name} using compression plugin (xz)")
            kwargs = {"preset": compresslevel} if compresslevel else {}
            with tarfile.open(tgz_path, f"w:xz", **kwargs) as tgz:
                for filename, abs_path in sorted(files.items()):
                    tgz.add(abs_path, filename, recursive=True)
            return tgz_path

        def tar_extract(src_path, destination_dir, *args, **kwargs):
            ConanOutput().info(f"Decompressing {os.path.basename(src_path)} using compression plugin (xz)")
            with open(src_path, mode='rb') as file_handler:
                the_tar = tarfile.open(fileobj=file_handler)
                the_tar.extraction_filter = (lambda member, path: member)
                the_tar.extractall(path=destination_dir)
                the_tar.close()
    """
    )

    c.save(
        {
            os.path.join(
                c.cache_folder, "extensions", "plugins", "compression.py"
            ): compression_plugin,
            "conanfile.py": GenConanfile("pkg", "1.0"),
        }
    )
    c.run("create .")
    c.run("cache save 'pkg/*'")
    assert "Compressing conan_cache_save.tgz using compression plugin (xz)" in c.out
    c.run("remove pkg/* -c")
    c.run("cache restore conan_cache_save.tgz")
    assert "Decompressing conan_cache_save.tgz using compression plugin (xz)" in c.out
    c.run("list pkg/1.0")
    assert "Found 1 pkg/version recipes matching pkg/1.0 in local cache" in c.out

    # Remove pre existing tgz to force a recompression
    c.run("remove pkg/* -c")
    c.run("create .")
    # Check the plugin is also used on remote interactions
    c.run("upload * -r=default -c")
    assert "Compressing conan_package.tgz using compression plugin (xz)" in c.out
    assert "pkg/1.0: Uploading recipe" in c.out
    c.run("remove pkg/* -c")
    c.run("download 'pkg/*' -r=default")
    assert "Decompressing conan_package.tgz using compression plugin (xz)" in c.out
