import os.path
import re

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient
from conans.util.files import save


def test_cache_clean():
    c = TestClient(default_server_user=True)
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

    c.run('cache clean "*" -s -b')
    assert not os.path.exists(pkg_layout.build())
    assert not os.path.exists(ref_layout.source())
    assert os.path.exists(ref_layout.download_export())
    assert os.path.exists(pkg_layout.download_package())

    c.run('cache clean -d')
    assert not os.path.exists(ref_layout.download_export())
    assert not os.path.exists(pkg_layout.download_package())


def test_cache_clean_all():
    c = TestClient()
    c.save({"pkg1/conanfile.py": GenConanfile("pkg", "0.1").with_class_attribute("revision_mode='scm'"),
            "pkg2/conanfile.py": GenConanfile("pkg", "0.2").with_package("error"),
            "pkg3/conanfile.py": GenConanfile("pkg", "0.3")})
    c.run("create pkg1", assert_error=True)
    c.run("create pkg2", assert_error=True)
    c.run("create pkg3")
    pref = c.created_package_reference("pkg/0.3")
    temp_folder = os.path.join(c.cache_folder, "p", "t")
    assert len(os.listdir(temp_folder)) == 1  # Failed export was here
    builds_folder = os.path.join(c.cache_folder, "p", "b")
    assert len(os.listdir(builds_folder)) == 2  # both builds are here
    c.run('cache clean')
    assert not os.path.exists(temp_folder)
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
    assert not os.path.exists(temp_folder)


def test_cache_multiple_builds_same_prev_clean():
    """
    Different consecutive builds will create exactly the same folder, for the
    same exact prev, not leaving trailing non-referenced folders
    """
    c = TestClient()
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
    c = TestClient()
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
    save(c.cache.global_conf_path, f"core.cache:storage_path={t}")
    c.save({"conanfile.py": GenConanfile("pkg", "0.1").with_cmake_build()})
    c.run("create .", assert_error=True)
    build_folder = re.search(r"pkg/0.1: Building your package in (\S+)", str(c.out)).group(1)
    assert os.listdir(build_folder)
    # now clean
    c.run("cache clean")
    assert not os.path.exists(build_folder)
