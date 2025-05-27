import os
import textwrap

from conan.internal.util.files import tar_extract
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def test_compression_plugin_not_valid():
    """Test an error is raised if the compression plugin is not valid"""

    c = TestClient()
    compression_plugin = textwrap.dedent(
        """
        def tar_compress(archive_path, files, recursive, conf=None, *args, **kwargs):
            pass
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
        def tar_compress(archive_path, files, recursive, conf=None, *args, **kwargs):
            name = os.path.basename(archive_path)
            ConanOutput().info(f"Compressing {name} using compression plugin (xz)")
            compresslevel = conf.get("core.gzip:compresslevel", check_type=int) if conf else None
            kwargs = {"preset": compresslevel} if compresslevel else {}
            with tarfile.open(archive_path, f"w:xz", **kwargs) as tgz:
                for filename, abs_path in sorted(files.items()):
                    tgz.add(abs_path, filename, recursive=True)

        def tar_extract(archive_path, dest_dir, conf=None, *args, **kwargs):
            ConanOutput().info(f"Decompressing {os.path.basename(archive_path)} using compression plugin (xz)")
            with open(archive_path, mode='rb') as file_handler:
                the_tar = tarfile.open(fileobj=file_handler)
                the_tar.extraction_filter = (lambda member, path: member)
                the_tar.extractall(path=dest_dir)
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


def test_compression_plugin_tar_not_compatible_with_builtin():
    """
    Test that built in tar_extract function fails when uncompressing a non compatible file (a file
    which has been compressed using the compression plugin with a different algorithm than the built-in one).
    """
    c = TestClient(default_server_user=True)

    compression_plugin = textwrap.dedent(
        """
        import os
        import zipfile
        from conan.api.output import ConanOutput

        # zip compression
        def tar_compress(archive_path, files, recursive, conf=None, *args, **kwargs):
            # compress files using zipfile library taking into account recursive
            name = os.path.basename(archive_path)
            compresslevel = conf.get("core.gzip:compresslevel", check_type=int) if conf else None
            ConanOutput().info(f"Compressing {name} using compression plugin (zip)")
            with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=compresslevel) as zipf:
                for filename, abs_path in sorted(files.items()):
                    if recursive:
                        arcname = os.path.relpath(abs_path, start=os.path.dirname(abs_path))
                        zipf.write(abs_path, arcname)
                    else:
                        zipf.write(abs_path, filename)

        def tar_extract(archive_path, dest_dir, conf=None, *args, **kwargs):
            # extract tar using zipfile library
            ConanOutput().info(f"Decompressing {os.path.basename(archive_path)} using compression plugin (zip)")
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                zip_ref.extractall(dest_dir)
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
    c.run("remove pkg/* -c")
    os.unlink(os.path.join(c.cache_folder, "extensions", "plugins", "compression.py"))
    c.run("cache restore conan_cache_save.tgz", assert_error=True)
    assert (
        "Error while extracting conan_cache_save.tgz. The file compression is not recogniced.\n"
        "This file could have been compressed using a `compression` plugin.\n"
        "If your organization uses this plugin, ensure it is correctly installed on your environment."
    ) in c.out


# https://github.com/conan-io/conan/issues/18259
def test_compress_in_subdirectory():
    c = TestClient(default_server_user=True)
    compression_plugin = textwrap.dedent(
        """
        import os
        import tarfile
        from conan.api.output import ConanOutput
        def tar_compress(archive_path, files, recursive, *args, **kwargs):
            # compress files using tarfile putting all content in a `conan/` subfolder
            name = os.path.basename(archive_path)
            ConanOutput().info(f"Compressing {os.path.basename(name)} in conan subfolder")
            with open(archive_path, "wb") as tgz_handle:
                tgz = tarfile.open(name, "w", fileobj=tgz_handle)
                for filename, abs_path in sorted(files.items()):
                    tgz.add(abs_path, os.path.join("conan", filename), recursive=recursive)
                tgz.close()

        def tar_extract(archive_path, dest_dir, *args, **kwargs):
            ConanOutput().info(f"Decompressing {archive_path} in conan subfolder")
            with open(archive_path, mode="rb") as file_handler:
                the_tar = tarfile.open(fileobj=file_handler)
                the_tar.extraction_filter = (lambda member, path: member)
                for member in the_tar.getmembers():
                    if member.name.startswith("conan/"):
                        member.name = member.name[len("conan/"):]  # Strip 'conan/' prefix
                        the_tar.extract(member, path=dest_dir)
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
    c.run("remove pkg/* -c")
    c.run("cache restore conan_cache_save.tgz")
    with open(os.path.join(c.current_folder, "conan_cache_save.tgz"), 'rb') as file_handler:
        dest_dir = os.path.join(c.cache_folder, "extracted")
        tar_extract(file_handler, dest_dir)
    assert os.listdir(dest_dir) == ["conan"]
    assert os.path.exists(os.path.join(dest_dir, "conan", "pkglist.json"))

