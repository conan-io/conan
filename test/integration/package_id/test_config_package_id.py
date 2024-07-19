import json

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient
from conans.util.files import save


@pytest.mark.parametrize("config_version, mode, result", [
    ("myconfig/1.2.3#rev1:pid1#prev1", "minor_mode", "myconfig/1.2.Z"),
    ("myconfig/1.2.3#rev1:pid1#prev1", "patch_mode", "myconfig/1.2.3"),
    ("myconfig/1.2.3#rev1:pid1#prev1", "full_mode", "myconfig/1.2.3#rev1:pid1"),
    ("myconfig/1.2.3#rev1:pid1#prev1", "revision_mode", "myconfig/1.2.3#rev1"),
    ("myconfig/1.2.3", "minor_mode", "myconfig/1.2.Z")])
def test_config_package_id(config_version, mode, result):
    c = TestClient()
    config_version = json.dumps({"config_version": [config_version]})
    save(c.cache.config_version_path, config_version)
    save(c.cache.global_conf_path, f"core.package_id:config_mode={mode}")
    c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
    c.run("create .")
    c.run("list pkg/0.1:* --format=json")
    info = json.loads(c.stdout)
    rrev = info["Local Cache"]["pkg/0.1"]["revisions"]["485dad6cb11e2fa99d9afbe44a57a164"]
    package_id = {"myconfig/1.2.Z": "c78b4d8224154390356fe04fe598d67aec930199",
                  "myconfig/1.2.3": "60005f5b11bef3ddd686b13f5c6bf576a9b882b8",
                  "myconfig/1.2.3#rev1:pid1": "b1525975eb5420cef45b4ddd1544f87c29c773a5",
                  "myconfig/1.2.3#rev1": "aae875ae226416f177bf386a3e4ad6aaffce09e7"}
    package_id = package_id.get(result)
    pkg = rrev["packages"][package_id]
    assert pkg["info"] == {"config_version": [result]}


def test_error_config_package_id():
    c = TestClient()
    c.save_home({"global.conf": "core.package_id:config_mode=minor_mode"})
    c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
    c.run("create .", assert_error=True)
    assert "ERROR: core.package_id:config_mode defined, " \
           "but error while loading 'config_version.json'" in c.out
