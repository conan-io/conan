import json
import os

import pytest

from conan.api.model import PkgReference
from conan.internal.util.files import save
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient

PKG_ID = "da39a3ee5e6b4b0d3255bfef95601890afd80709"
RREV = "a9ec2e5fbb166568d4670a9cd1ef4b26"


@pytest.fixture(scope="module")
def client():
    tc = TestClient(light=True, default_server_user=True)
    tc.save({"conanfile.py": GenConanfile("pkg")})
    tc.run("create . --version=1.0")
    assert RREV == tc.exported_recipe_revision()
    assert PKG_ID == tc.created_package_id("pkg/1.0")
    tc.run("upload * -r=default -c")
    tc.run("remove * -c")
    tc.run("remote update default --recipes-only")
    return tc


def test_graph_binary_analyze(client):
    client.run("install --requires=pkg/1.0 -f=json", assert_error=True)
    client.assert_listed_binary({"pkg/1.0": (PKG_ID, "Missing")})

    client.run("graph explain --requires=pkg/1.0")
    assert "ERROR: No package binaries exist" in client.out


def test_list_packages(client):
    client.run("list pkg/1.0:* -r=default -f=json", redirect_stdout="list.json")
    result = json.loads(client.load("list.json"))
    assert len(result["default"]["pkg/1.0"]["revisions"][RREV]["packages"]) == 0

    client.run(f"list pkg/1.0:{PKG_ID} -r=default -f=json", redirect_stdout="list.json")
    result = json.loads(client.load("list.json"))
    assert "error" in result["default"]  # not found error


def test_download_package(client):
    client.run("download pkg/1.0:* -r=default -f=json", redirect_stdout="download.json")
    result = json.loads(client.load("download.json"))
    assert len(result["Local Cache"]["pkg/1.0"]["revisions"][RREV]["packages"]) == 0


def test_remove_package(client):
    client.run(f"remove pkg/1.0:{PKG_ID} -r=default -c -f=json", redirect_stdout="remove.json")
    result = json.loads(client.load("remove.json"))
    assert result["default"] == {}

    client.run(f"remove pkg/1.0:* -r=default -c -f=json", redirect_stdout="remove.json")
    result = json.loads(client.load("remove.json"))
    assert result["default"] == {}

    client.run(f"remove pkg/1.0 -r=default -c -f=json", redirect_stdout="remove.json")
    result = json.loads(client.load("remove.json"))
    assert "packages" not in result["default"]["pkg/1.0"]["revisions"][RREV]


@pytest.mark.parametrize("pattern", ["*", "pkg/2.0", "pkg/2.0:*", f"pkg/2.0:{PKG_ID}"])
def test_upload_still_works(client, pattern):
    client.run("create . --version=2.0")
    layout = client.created_layout()
    save(os.path.join(layout.metadata(), "metadata.log"), "New hello")

    client.run(f"upload {pattern} -r=default -c")

    # Now check that the binary was in fact uploaded
    client.run("remote update default --recipes-only=False")
    client.run("remove * -c")
    client.run("list pkg/2.0:* -r=default -f=json", redirect_stdout="list.json")
    result = json.loads(client.load("list.json"))
    assert len(result["default"]["pkg/2.0"]["revisions"][RREV]["packages"]) == 1
    assert PKG_ID in result["default"]["pkg/2.0"]["revisions"][RREV]["packages"]

    client.run(f"download {pattern} -r=default -f=json --metadata=*", redirect_stdout="download.json")
    pkg2_layout = client.get_latest_pkg_layout(PkgReference().loads(f"pkg/2.0#{RREV}:{PKG_ID}"))
    assert os.path.exists(os.path.join(pkg2_layout.metadata(), "metadata.log"))
