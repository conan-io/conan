import hashlib
import json
import os.path
import re
import textwrap

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.file_server import TestFileServer
from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient
from conan.internal.util.files import save, load


@pytest.mark.parametrize("use_pkglist", [True, False])
def test_cache_clean(use_pkglist):
    c = TestClient(default_server_user=True, light=True)
    c.save({"conanfile.py": GenConanfile("pkg", "0.1").with_exports("*").with_exports_sources("*"),
            "sorces/file.txt": ""})
    c.run("create .")
    ref_layout = c.exported_layout()
    pkg_layout = c.created_layout()
    c.run("upload * -c -r=default")  # Force creation of tgzs
    assert os.path.exists(ref_layout.source())
    assert os.path.exists(ref_layout.download_export())
    assert os.path.exists(pkg_layout.build())
    assert os.path.exists(pkg_layout.download_package())

    if use_pkglist:
        c.run("list *:*#* -f=json", redirect_stdout="pkglist.json")
    arg = "--list=pkglist.json" if use_pkglist else "*"
    c.run(f'cache clean {arg} -s -b -v')
    assert f"{ref_layout.reference.repr_notime()}: Cleaning recipe cache contents" in c.out
    assert f"{pkg_layout.reference}: Cleaning package cache contents" in c.out
    assert not os.path.exists(pkg_layout.build())
    assert not os.path.exists(ref_layout.source())
    assert os.path.exists(ref_layout.download_export())
    assert os.path.exists(pkg_layout.download_package())

    c.run('cache clean -d')
    assert not os.path.exists(ref_layout.download_export())
    assert not os.path.exists(pkg_layout.download_package())

    c.run("cache clean -bs -v")
    assert "Cleaning 0 backup sources" in c.out


def _recipe_with_backup_source(file_server, name, version="1.0"):
    """ A recipe that downloads its own file in the source() method, so it generates a backup
    source, that will be associated to this recipe in the backup sources metadata
    """
    content = f"{name} sources"
    save(os.path.join(file_server.store, "internet", f"{name}.txt"), content)
    sha256 = hashlib.sha256(content.encode()).hexdigest()
    attrs = "" if name == "unknown" else f'name = "{name}"; version = "{version}"'
    return textwrap.dedent(f"""
        from conan import ConanFile
        from conan.tools.files import download
        class Pkg(ConanFile):
            {attrs}
            def source(self):
                download(self, "{file_server.fake_url}/internet/{name}.txt", "{name}.txt",
                         sha256="{sha256}")
        """)


@pytest.mark.parametrize("use_pkglist", [True, False])
def test_cache_clean_backup_sources_only_selected(use_pkglist):
    """ Cleaning the backup sources of some recipes must not remove the extra backup sources of
    other recipes, neither the ones that do not belong to any recipe in the cache. Those can be
    in the download cache if their recipe was removed from the Conan cache, if they were
    downloaded by a local conanfile (conan source), or if the download cache is shared with other
    Conan homes. Only a clean without pattern nor list removes them
    """
    c = TestClient(light=True)
    file_server = TestFileServer()
    c.servers["file_server"] = file_server
    download_cache = temp_folder()
    c.save_home({"global.conf": f"core.sources:download_cache={download_cache}"})
    backups = os.path.join(download_cache, "s")

    def backup_sources_references():
        refs = set()
        for f in os.listdir(backups):
            if f.endswith(".json"):
                refs.update(json.loads(load(os.path.join(backups, f)))["references"])
        return refs

    for name in ("pkg", "other", "removed"):
        c.save({"conanfile.py": _recipe_with_backup_source(file_server, name)})
        c.run("create .")
    c.run("remove removed/1.0 -c")  # Its backup source is not removed
    c.save({"conanfile.py": _recipe_with_backup_source(file_server, "unknown")})
    c.run("source .")  # A local conanfile, not in the cache
    assert backup_sources_references() == {"pkg/1.0", "other/1.0", "removed/1.0", "unknown"}

    def clean(pattern):
        if use_pkglist:
            c.run(f"list {pattern}:*#* -f=json", redirect_stdout="pkglist.json")
            c.run("cache clean --list=pkglist.json -bs")
        else:
            c.run(f"cache clean {pattern} -bs")

    clean("pkg/*")
    # Only the backup sources of the selected pkg were removed, not the extra ones
    assert backup_sources_references() == {"other/1.0", "removed/1.0", "unknown"}
    clean("*")
    # The backup sources of the recipes in the cache are removed, the extra ones still not
    assert backup_sources_references() == {"removed/1.0", "unknown"}
    c.run("cache clean -bs")
    # Only without pattern nor list, the extra ones are also removed
    assert os.listdir(backups) == []


def test_cache_clean_all():
    c = TestClient(light=True)
    c.save({"pkg1/conanfile.py": GenConanfile("pkg", "0.1").with_class_attribute("revision_mode='scm'"),
            "pkg2/conanfile.py": GenConanfile("pkg", "0.2").with_package("error"),
            "pkg3/conanfile.py": GenConanfile("pkg", "0.3")})
    c.run("create pkg1", assert_error=True)
    c.run("create pkg2", assert_error=True)
    c.run("create pkg3")
    pref = c.created_package_reference("pkg/0.3")
    tmp_folder = os.path.join(c.cache_folder, "p", "t")
    assert len(os.listdir(tmp_folder)) == 1  # Failed export was here
    builds_folder = os.path.join(c.cache_folder, "p", "b")
    assert len(os.listdir(builds_folder)) == 2  # both builds are here
    c.run('cache clean')
    assert not os.path.exists(tmp_folder)
    assert len(os.listdir(builds_folder)) == 1  # only correct pkg/0.3 remains
    # Check correct package removed all
    ref_layout = c.get_latest_ref_layout(pref.ref)
    pkg_layout = c.get_latest_pkg_layout(pref)
    assert not os.path.exists(ref_layout.source())
    assert not os.path.exists(ref_layout.download_export())
    assert not os.path.exists(pkg_layout.build())
    assert not os.path.exists(pkg_layout.download_package())

    # A second clean like this used to crash
    # as it tried to delete a folder that was not there and tripped shutils up
    c.run('cache clean')
    assert not os.path.exists(tmp_folder)


def test_cache_multiple_builds_same_prev_clean():
    """
    Different consecutive builds will create exactly the same folder, for the
    same exact prev, not leaving trailing non-referenced folders
    """
    c = TestClient(light=True)
    c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
    c.run("create .")
    create_out = c.out
    c.run("cache path pkg/0.1:da39a3ee5e6b4b0d3255bfef95601890afd80709")
    path1 = str(c.stdout)
    assert path1 in create_out
    c.run("create .")
    create_out = c.out
    c.run("cache path pkg/0.1:da39a3ee5e6b4b0d3255bfef95601890afd80709")
    path2 = str(c.stdout)
    assert path2 in create_out
    assert path1 == path2

    builds_folder = os.path.join(c.cache_folder, "p", "b")
    assert len(os.listdir(builds_folder)) == 1  # only one build
    c.run('cache clean')
    assert len(os.listdir(builds_folder)) == 1  # one build not cleaned
    c.run('remove * -c')
    assert len(os.listdir(builds_folder)) == 0  # no folder remain


def test_cache_multiple_builds_diff_prev_clean():
    """
    Different consecutive builds will create different folders, even if for the
    same exact prev, leaving trailing non-referenced folders
    """
    c = TestClient(light=True)
    package_lines = 'save(self, os.path.join(self.package_folder, "foo.txt"), str(time.time()))'
    gen = GenConanfile("pkg", "0.1").with_package(package_lines).with_import("import os, time") \
                                    .with_import("from conan.tools.files import save")
    c.save({"conanfile.py": gen})
    c.run("create .")
    create_out = c.out
    c.run("cache path pkg/0.1:da39a3ee5e6b4b0d3255bfef95601890afd80709")
    path1 = str(c.stdout)
    assert path1 in create_out
    c.run("create .")
    create_out = c.out
    c.run("cache path pkg/0.1:da39a3ee5e6b4b0d3255bfef95601890afd80709")
    path2 = str(c.stdout)
    assert path2 in create_out
    assert path1 != path2

    builds_folder = os.path.join(c.cache_folder, "p", "b")
    assert len(os.listdir(builds_folder)) == 2  # both builds are here
    c.run('cache clean')
    assert len(os.listdir(builds_folder)) == 2  # two builds will remain, both are valid
    c.run('remove * -c')
    assert len(os.listdir(builds_folder)) == 0  # no folder remain


def test_cache_clean_custom_storage():
    c = TestClient()
    t = temp_folder(path_with_spaces=False)
    save(c.paths.global_conf_path, f"core.cache:storage_path={t}")
    c.save({"conanfile.py": GenConanfile("pkg", "0.1").with_cmake_build()})
    c.run("create .", assert_error=True)
    build_folder = re.search(r"Building your package in (\S+)", str(c.out)).group(1)
    assert os.listdir(build_folder)
    # now clean
    c.run("cache clean")
    assert not os.path.exists(build_folder)
