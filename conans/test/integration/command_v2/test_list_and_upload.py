import pytest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


@pytest.fixture()
def client():
    c = TestClient(default_server_user=True)
    c.save({
        "zlib.py": GenConanfile("zlib"),
        "zli.py": GenConanfile("zli", "1.0.0")
    })
    c.run("create zli.py")
    c.run("create zlib.py --version=1.0.0 --user=user --channel=channel")
    return c


class TestListUpload:
    refs = ["zli/1.0.0#f034dc90894493961d92dd32a9ee3b78",
            "zlib/1.0.0@user/channel#ffd4bc45820ddb320ab224685b9ba3fb"]

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
        assert str(client.out).count("Uploading package") == 2


class TestGraphCreatedUpload:
    def test_create_upload(self):
        c = TestClient(default_server_user=True)
        c.save({"zlib/conanfile.py": GenConanfile("zlib", "1.0"),
                "app/conanfile.py": GenConanfile("app", "1.0").with_requires("zlib/1.0")})
        c.run("create zlib")
        c.run("create app --format=json", redirect_stdout="graph.json")
        c.run("list --graph=graph.json --format=json", redirect_stdout="pkglist.json")
        c.run("upload --list=pkglist.json -r=default")
        assert "Uploading recipe 'app/1.0#0fa1ff1b90576bb782600e56df642e19'" in c.out
        assert "Uploading recipe 'zlib/1.0#c570d63921c5f2070567da4bf64ff261'" in c.out
        assert "Uploading package 'app" in c.out


class TestGraphPkgList:
    def test_graph_pkg_list(self):
        c = TestClient()
        c.save({"zlib/conanfile.py": GenConanfile("zlib", "1.0"),
                "app/conanfile.py": GenConanfile("app", "1.0").with_requires("zlib/1.0")})
        c.run("create zlib")
        c.run("create app --format=json", redirect_stdout="graph.json")
        c.run("list --graph=graph.json --graph-binaries=build --format=json",
              redirect_stdout="pkglist.json")
        pkglist = c.load("pkglist.json")
        assert "app/1.0" in pkglist
        assert "zlib" not in pkglist
