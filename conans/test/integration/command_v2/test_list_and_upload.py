import time

import pytest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient
from conans.util.env import environment_update


# TODO: optimize this fixture
@pytest.fixture()
def client():
    c = TestClient(default_server_user=True)
    c.save({
        "zlib.py": GenConanfile("zlib"),
        "zlib_ng.py": GenConanfile("zlib_ng", "1.0.0"),
        "zli.py": GenConanfile("zli", "1.0.0"),
        "zli_rev2.py": GenConanfile("zli", "1.0.0").with_settings("os")
                                                   .with_package_file("f.txt", env_var="MYREV"),
        "zlix.py": GenConanfile("zlix", "1.0.0")
    })
    c.run("create zli.py")
    c.run("create zlib.py --version=1.0.0 --user=user --channel=channel")
    c.run("create zlib.py --version=2.0.0 --user=user --channel=channel")
    c.run("create zlix.py")

    time.sleep(1.0)
    # We create and upload new revisions later, to avoid timestamp overlaps (low resolution)
    with environment_update({"MYREV": "0"}):
        c.run("create zli_rev2.py -s os=Windows")
        c.run("create zli_rev2.py -s os=Linux")
    with environment_update({"MYREV": "42"}):
        c.run("create zli_rev2.py -s os=Windows")
    return c


class TestListUpload:
    refs = ["zli/1.0.0#b58eeddfe2fd25ac3a105f72836b3360",
            "zlib/1.0.0@user/channel#ffd4bc45820ddb320ab224685b9ba3fb",
            "zlib/2.0.0@user/channel#ffd4bc45820ddb320ab224685b9ba3fb",
            "zlix/1.0.0#81f598d1d8648389bb7d0494fffb654e"]

    def test_list_upload_recipes(self, client):
        pattern = "z*#latest"
        client.run(f"list {pattern} --format=json", redirect_stdout="pkglist.json")
        client.run("upload --list=pkglist.json -r=default")
        for r in self.refs:
            assert f"Uploading recipe '{r}'" in client.out
        assert "Uploading package" not in client.out

    def test_list_upload_packages(self, client):
        pattern = "z*#latest:*#latest"
        client.run(f"list {pattern} --format=json", redirect_stdout="pkglist.json")
        client.run("upload --list=pkglist.json -r=default")
        for r in self.refs:
            assert f"Uploading recipe '{r}'" in client.out
        assert str(client.out).count("Uploading package") == 5


class TestGraphCreatedUpload:
    def test_graph_created_upload(self):
        c = TestClient(default_server_user=True)
        c.save({"zlib/conanfile.py": GenConanfile("zlib", "1.0"),
                "app/conanfile.py": GenConanfile("app", "1.0").with_requires("zlib/1.0")})
        c.run("create zlib")
        c.run("create app --format=json", redirect_stdout="graph.json")
        c.run("list --graph=graph.json --format=json", redirect_stdout="pkglist.json")
        c.run("upload --list=pkglist.json -r=default")
        assert "Uploading recipe 'app/1.0#0fa1ff1b90576bb782600e56df642e19'" in c.out
        assert "zlib" not in c.out
        assert "Uploading package 'app" in c.out
