import os.path

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_cache_clean():
    c = TestClient(default_server_user=True)
    c.save({"conanfile.py": GenConanfile("pkg", "0.1").with_exports("*").with_exports_sources("*"),
            "sorces/file.txt": ""})
    c.run("create .")
    pref = c.created_package_reference("pkg/0.1")
    c.run("upload * -c -r=default")  # Force creation of tgzs
    ref_layout = c.get_latest_ref_layout(pref.ref)
    pkg_layout = c.get_latest_pkg_layout(pref)
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
