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

    c.run('cache clean "*" -d')
    assert not os.path.exists(ref_layout.download_export())
    assert not os.path.exists(pkg_layout.download_package())


def test_cache_clean_noargs_error():
    c = TestClient()
    c.run('cache clean "*"', assert_error=True)
    assert "Define at least one argument among [--source, --build, --download]" in c.out
