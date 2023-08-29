import json

import pytest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


class TestListUpload:
    refs = ["zli/1.0.0#f034dc90894493961d92dd32a9ee3b78",
            "zlib/1.0.0@user/channel#ffd4bc45820ddb320ab224685b9ba3fb"]

    @pytest.fixture()
    def client(self):
        c = TestClient(default_server_user=True)
        c.save({
            "zlib.py": GenConanfile("zlib"),
            "zli.py": GenConanfile("zli", "1.0.0")
        })
        c.run("create zli.py")
        c.run("create zlib.py --version=1.0.0 --user=user --channel=channel")
        return c

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

    def test_list_upload_empty_list(self, client):
        client.run(f"install --requires=zlib/1.0.0@user/channel -f json",
                   redirect_stdout="install_graph.json")

        # Generate an empty pkglist.json
        client.run(f"list --format=json --graph=install_graph.json --graph-binaries=bogus",
                   redirect_stdout="pkglist.json")

        # No binaries should be uploaded since the pkglist is empty, but the command
        # should not error
        client.run("upload --list=pkglist.json -r=default")
        assert "No packages were uploaded because the package list is empty." in client.out


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
        assert "Uploading package 'zlib" in c.out


class TestCreateGraphToPkgList:
    def test_graph_pkg_list_only_built(self):
        c = TestClient()
        c.save({"zlib/conanfile.py": GenConanfile("zlib", "1.0"),
                "app/conanfile.py": GenConanfile("app", "1.0").with_requires("zlib/1.0")})
        c.run("create zlib")
        c.run("create app --format=json", redirect_stdout="graph.json")
        c.run("list --graph=graph.json --graph-binaries=build --format=json")
        pkglist = json.loads(c.stdout)["Local Cache"]
        assert len(pkglist) == 1
        assert len(pkglist["app/1.0"]["revisions"]
                   ["0fa1ff1b90576bb782600e56df642e19"]["packages"]) == 1

    def test_graph_pkg_list_all_recipes_only(self):
        """
        --graph-recipes=* selects all the recipes in the graph
        """
        c = TestClient()
        c.save({"zlib/conanfile.py": GenConanfile("zlib", "1.0"),
                "app/conanfile.py": GenConanfile("app", "1.0").with_requires("zlib/1.0")})
        c.run("create zlib")
        c.run("create app --format=json", redirect_stdout="graph.json")
        c.run("list --graph=graph.json --graph-recipes=* --format=json")
        pkglist = json.loads(c.stdout)["Local Cache"]
        assert len(pkglist) == 2
        assert "packages" not in pkglist["app/1.0"]["revisions"]["0fa1ff1b90576bb782600e56df642e19"]
        assert "packages" not in pkglist["zlib/1.0"]["revisions"]["c570d63921c5f2070567da4bf64ff261"]

    def test_graph_pkg_list_python_requires(self):
        """
        include python_requires too
        """
        c = TestClient(default_server_user=True)
        c.save({"pytool/conanfile.py": GenConanfile("pytool", "0.1"),
                "zlib/conanfile.py": GenConanfile("zlib", "1.0").with_python_requires("pytool/0.1"),
                "app/conanfile.py": GenConanfile("app", "1.0").with_requires("zlib/1.0")})
        c.run("create pytool")
        c.run("create zlib")
        c.run("upload * -c -r=default")
        c.run("remove * -c")
        c.run("create app --format=json", redirect_stdout="graph.json")
        c.run("list --graph=graph.json --format=json")
        pkglist = json.loads(c.stdout)["Local Cache"]
        assert len(pkglist) == 3
        assert "96aec08148a2392127462c800e1c8af6" in pkglist["pytool/0.1"]["revisions"]
        pkglist = json.loads(c.stdout)["default"]
        assert len(pkglist) == 2
        assert "96aec08148a2392127462c800e1c8af6" in pkglist["pytool/0.1"]["revisions"]

    def test_graph_pkg_list_create_python_requires(self):
        """
        include python_requires too
        """
        c = TestClient(default_server_user=True)
        c.save({"conanfile.py": GenConanfile("pytool", "0.1").with_package_type("python-require")})
        c.run("create . --format=json", redirect_stdout="graph.json")
        c.run("list --graph=graph.json --format=json")
        pkglist = json.loads(c.stdout)["Local Cache"]
        assert len(pkglist) == 1
        assert "62a6a9e5347b789bfc6572948ea19f85" in pkglist["pytool/0.1"]["revisions"]


class TestGraphInfoToPkgList:
    def test_graph_pkg_list_only_built(self):
        c = TestClient(default_server_user=True)
        c.save({"zlib/conanfile.py": GenConanfile("zlib", "1.0"),
                "app/conanfile.py": GenConanfile("app", "1.0").with_requires("zlib/1.0")})
        c.run("create zlib")
        c.run("create app --format=json")
        c.run("upload * -c -r=default")
        c.run("remove * -c")
        c.run("graph info --requires=app/1.0 --format=json", redirect_stdout="graph.json")
        c.run("list --graph=graph.json --graph-binaries=build --format=json")
        pkglist = json.loads(c.stdout)
        assert len(pkglist["Local Cache"]) == 0
        assert len(pkglist["default"]) == 2
        c.run("install --requires=app/1.0 --format=json", redirect_stdout="graph.json")
        c.run("list --graph=graph.json --graph-binaries=download --format=json")
        pkglist = json.loads(c.stdout)
        assert len(pkglist["Local Cache"]) == 2
        assert len(pkglist["default"]) == 2
        c.run("list --graph=graph.json --graph-binaries=build --format=json")
        pkglist = json.loads(c.stdout)
        assert len(pkglist["Local Cache"]) == 0
        assert len(pkglist["default"]) == 2


class TestDownloadUpload:
    @pytest.fixture()
    def client(self):
        c = TestClient(default_server_user=True)
        c.save({
            "zlib.py": GenConanfile("zlib"),
            "zli.py": GenConanfile("zli", "1.0.0")
        })
        c.run("create zli.py")
        c.run("create zlib.py --version=1.0.0 --user=user --channel=channel")
        c.run("upload * -r=default -c")
        c.run("remove * -c")
        return c

    @pytest.mark.parametrize("prev_list", [False, True])
    def test_download_upload_all(self, client, prev_list):
        # We need to be consequeent with the pattern, it is not the same defaults for
        # download and for list
        pattern = "zlib/*#latest:*#latest"
        if prev_list:
            client.run(f"list {pattern} -r=default --format=json", redirect_stdout="pkglist.json")
            # Overwriting previous pkglist.json
            pattern = "--list=pkglist.json"

        client.run(f"download {pattern} -r=default --format=json", redirect_stdout="pkglist.json")
        # TODO: Discuss "origin"
        assert "Local Cache" in client.load("pkglist.json")
        client.run("remove * -r=default -c")
        client.run("upload --list=pkglist.json -r=default")
        assert f"Uploading recipe 'zlib/1.0.0" in client.out
        assert f"Uploading recipe 'zli/" not in client.out
        assert "Uploading package 'zlib/1.0.0" in client.out
        assert "Uploading package 'zli/" not in client.out

    @pytest.mark.parametrize("prev_list", [False, True])
    def test_download_upload_only_recipes(self, client, prev_list):
        if prev_list:
            pattern = "zlib/*#latest"
            client.run(f"list {pattern} -r=default --format=json", redirect_stdout="pkglist.json")
            # Overwriting previous pkglist.json
            pattern = "--list=pkglist.json"
        else:
            pattern = "zlib/*#latest --only-recipe"
        client.run(f"download {pattern} -r=default --format=json", redirect_stdout="pkglist.json")
        # TODO: Discuss "origin"
        assert "Local Cache" in client.load("pkglist.json")
        # Download binary too! Just to make sure it is in the cache, but not uploaded
        # because it is not in the orignal list of only recipes
        client.run(f"download * -r=default")
        client.run("remove * -r=default -c")
        client.run("upload --list=pkglist.json -r=default")
        assert f"Uploading recipe 'zlib/1.0.0" in client.out
        assert f"Uploading recipe 'zli/" not in client.out
        assert "Uploading package 'zlib/1.0.0" not in client.out
        assert "Uploading package 'zli/" not in client.out


class TestListRemove:
    @pytest.fixture()
    def client(self):
        c = TestClient(default_server_user=True)
        c.save({
            "zlib.py": GenConanfile("zlib"),
            "zli.py": GenConanfile("zli", "1.0.0")
        })
        c.run("create zli.py")
        c.run("create zlib.py --version=1.0.0 --user=user --channel=channel")
        c.run("upload * -r=default -c")
        return c

    def test_remove_nothing_only_refs(self, client):
        # It is necessary to do *#* for actually removing something
        client.run(f"list * --format=json", redirect_stdout="pkglist.json")
        client.run(f"remove --list=pkglist.json -c")
        assert "Nothing to remove, package list do not contain recipe revisions" in client.out

    @pytest.mark.parametrize("remote", [False, True])
    def test_remove_all(self, client, remote):
        # It is necessary to do *#* for actually removing something
        remote = "-r=default" if remote else ""
        client.run(f"list *#* {remote} --format=json", redirect_stdout="pkglist.json")
        client.run(f"remove --list=pkglist.json {remote} -c")
        assert "zli/1.0.0#f034dc90894493961d92dd32a9ee3b78:" \
               " Removed recipe and all binaries" in client.out
        assert "zlib/1.0.0@user/channel#ffd4bc45820ddb320ab224685b9ba3fb:" \
               " Removed recipe and all binaries" in client.out
        client.run(f"list * {remote}")
        assert "There are no matching recipe references" in client.out

    @pytest.mark.parametrize("remote", [False, True])
    def test_remove_packages_no_revisions(self, client, remote):
        # It is necessary to do *#* for actually removing something
        remote = "-r=default" if remote else ""
        client.run(f"list *#*:* {remote} --format=json", redirect_stdout="pkglist.json")
        client.run(f"remove --list=pkglist.json {remote} -c")
        assert "No binaries to remove for 'zli/1.0.0#f034dc90894493961d92dd32a9ee3b78'" in client.out
        assert "No binaries to remove for 'zlib/1.0.0@user/channel" \
               "#ffd4bc45820ddb320ab224685b9ba3fb" in client.out

    @pytest.mark.parametrize("remote", [False, True])
    def test_remove_packages(self, client, remote):
        # It is necessary to do *#* for actually removing something
        remote = "-r=default" if remote else ""
        client.run(f"list *#*:*#* {remote} --format=json", redirect_stdout="pkglist.json")
        client.run(f"remove --list=pkglist.json {remote} -c")

        assert "Removed recipe and all binaries" not in client.out
        assert "zli/1.0.0#f034dc90894493961d92dd32a9ee3b78: Removed binaries" in client.out
        assert "zlib/1.0.0@user/channel#ffd4bc45820ddb320ab224685b9ba3fb: " \
               "Removed binaries" in client.out
        client.run(f"list *:* {remote}")
        assert "zli/1.0.0" in client.out
        assert "zlib/1.0.0@user/channel" in client.out
