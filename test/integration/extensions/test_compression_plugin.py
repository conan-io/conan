import os
import textwrap


from conan.internal.util.files import load
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def test_compression_plugin_not_valid():
    """Test an error is raised if the compression plugin is not valid"""
    c = TestClient(light=True)
    c.save_home({"extensions/plugins/compression.py": ""})
    c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
    c.run("create .", assert_error=True)
    assert "ERROR: The 'compression.py' plugin does not contain" in c.out


def test_compression_plugin_fallbacks():
    """If the plugin methods returns False, fallback to Conan behavior"""

    c = TestClient(default_server_user=True, light=True)
    compression_plugin = textwrap.dedent("""\
        import os
        from conan.api.output import ConanOutput

        def tar_compress(archive_path, files, recursive, scope=None, compresslevel=None,
                         *args, **kwargs):
            name = os.path.basename(archive_path)
            ConanOutput(scope=scope).info(f"Falling back to compress {name} with Conan!")
            return False

        def tar_extract(archive_path, dest_dir, scope=None, *args, **kwargs):
            name = os.path.basename(archive_path)
            ConanOutput(scope=scope).info(f"Falling back to extract {name} with Conan!")
            return False
    """)
    c.save_home({"extensions/plugins/compression.py": compression_plugin})
    c.save({"conanfile.py": GenConanfile("pkg", "1.0").with_exports("*.txt")
                                                      .with_package_file("some.lib", "lib"),
            "myexportfile.txt": "something"})

    c.run("create .")
    c.run("upload * -r=default -c")
    assert "pkg/1.0: Falling back to compress conan_export.tgz with Conan!" in c.out
    assert "Falling back to compress conan_package.tgz with Conan!" in c.out
    c.run("remove * -c")
    c.run("install --requires=pkg/1.0")
    assert "pkg/1.0: Falling back to extract conan_export.tgz with Conan!" in c.out
    assert "pkg/1.0: Falling back to extract conan_package.tgz with Conan!" in c.out

    # same for cache save/restore
    c.run("cache save *:*")
    assert "Falling back to compress conan_cache_save.tgz with Conan!" in c.out

    c.run("remove * -c")
    c.run("cache restore conan_cache_save.tgz")
    assert "Restore: Falling back to extract conan_cache_save.tgz with Conan!" in c.out
    c.run("cache path pkg/1.0")
    path = str(c.stdout).strip()
    assert load(os.path.join(path, "myexportfile.txt")) == "something"
    c.run(f"cache path pkg/1.0:da39a3ee5e6b4b0d3255bfef95601890afd80709")
    path = str(c.stdout).strip()
    assert load(os.path.join(path, "some.lib")) == "lib"


def test_compression_plugin_correctly_load():
    """Test that the compression plugin is correctly loaded and used on:
    - cache save/restore
    - remote upload/download
    """
    c = TestClient(default_server_user=True, light=True)

    compression_plugin = textwrap.dedent("""\
        import os, tarfile
        from conan.api.output import ConanOutput

        def tar_compress(archive_path, files, recursive, scope=None, compresslevel=None,
                         *args, **kwargs):
            name = os.path.basename(archive_path)
            assert name.endswith("xz")
            ConanOutput(scope=scope).info(f"Compressing {name} with my Plugin!")
            with tarfile.open(archive_path, f"w:xz", preset=compresslevel,
                              format=tarfile.PAX_FORMAT) as tgz:
                for filename, abs_path in sorted(files.items()):
                    tgz.add(abs_path, filename, recursive=recursive)

        def tar_extract(archive_path, dest_dir, scope=None, *args, **kwargs):
            name = os.path.basename(archive_path)
            ConanOutput(scope=scope).info(f"Extracting {name} with my Plugin!")
            with open(archive_path, mode='rb') as file_handler:
                the_tar = tarfile.open(fileobj=file_handler)
                the_tar.extraction_filter = (lambda member, path: member)
                the_tar.extractall(path=dest_dir)
                the_tar.close()
        """)

    c.save_home({"extensions/plugins/compression.py": compression_plugin})
    c.save({"conanfile.py": GenConanfile("pkg", "1.0").with_exports("*.txt")
                                                      .with_package_file("some.lib", "lib"),
            "myexportfile.txt": "something"})

    c.run("create .")
    c.run("upload * -r=default -c -cc core.upload:compression_format=xz")
    assert "pkg/1.0: Compressing conan_export.txz with my Plugin!" in c.out
    assert "Compressing conan_package.txz with my Plugin!" in c.out

    c.run("remove * -c")
    c.run("install --requires=pkg/1.0")
    assert "pkg/1.0: Extracting conan_export.txz with my Plugin!" in c.out
    assert "pkg/1.0: Extracting conan_package.txz with my Plugin!" in c.out

    # same for cache save/restore
    c.run("cache save *:* --file=save.txz")
    assert "Compressing save.txz with my Plugin!" in c.out

    c.run("remove * -c")
    c.run("cache restore save.txz")
    assert "Restore: Extracting save.txz with my Plugin!" in c.out

    c.run("cache path pkg/1.0")
    path = str(c.stdout).strip()
    assert load(os.path.join(path, "myexportfile.txt")) == "something"
    c.run(f"cache path pkg/1.0:da39a3ee5e6b4b0d3255bfef95601890afd80709")
    path = str(c.stdout).strip()
    assert load(os.path.join(path, "some.lib")) == "lib"


def test_compress_in_subdirectory():
    # https://github.com/conan-io/conan/issues/18259
    c = TestClient(light=True)

    compression_plugin = textwrap.dedent("""\
        import os, tarfile
        from conan.api.output import ConanOutput

        def tar_compress(archive_path, files, recursive, scope=None, compresslevel=None,
                        *args, **kwargs):
            name = os.path.basename(archive_path)
            assert name.endswith("xz")
            ConanOutput(scope=scope).info(f"Compressing {name} with my Plugin!")
            with tarfile.open(archive_path, f"w:xz", preset=compresslevel,
                         format=tarfile.PAX_FORMAT) as tgz:
                for filename, abs_path in sorted(files.items()):
                    tgz.add(abs_path, os.path.join("conan", filename), recursive=recursive)

        def tar_extract(archive_path, dest_dir, scope=None, *args, **kwargs):
            name = os.path.basename(archive_path)
            ConanOutput(scope=scope).info(f"Extracting {name} with my Plugin!")
            with open(archive_path, mode='rb') as file_handler:
                the_tar = tarfile.open(fileobj=file_handler)
                the_tar.extraction_filter = (lambda member, path: member)

                for member in the_tar.getmembers():
                    if member.name.startswith("conan/"):
                        member.name = member.name[len("conan/"):]  # Strip 'conan/' prefix
                    the_tar.extract(member, path=dest_dir)
                the_tar.close()
           """)

    c.save_home({"extensions/plugins/compression.py": compression_plugin})
    c.save({"conanfile.py": GenConanfile("pkg", "1.0").with_exports("*.txt"),
            "myexportfile.txt": "something"})

    c.run("create .")

    c.run("cache save *:* --file=save.txz")
    assert "Compressing save.txz with my Plugin!" in c.out

    c.run("remove * -c")
    c.run("cache restore save.txz")
    assert "Restore: Extracting save.txz with my Plugin!" in c.out

    c.run("cache path pkg/1.0")
    path = str(c.stdout).strip()
    assert load(os.path.join(path, "myexportfile.txt")) == "something"
