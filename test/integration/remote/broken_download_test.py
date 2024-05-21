import json
import os

import pytest
from requests import Response

from requests.exceptions import ConnectionError

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient, TestRequester, TestServer
from conans.util.files import save


class TestBrokenDownload:

    @pytest.fixture()
    def setup(self):
        server = TestServer()
        client = TestClient(servers={"default": server}, inputs=["admin", "password"])
        client.save({"conanfile.py": GenConanfile("hello", "0.1")})
        client.run("create .")
        pref = client.created_package_reference("hello/0.1")
        client.run("upload * -r default -c")
        client.run("remove * -c")
        return client, pref

    def test_corrupt_export_tgz(self, setup):
        client, pref = setup
        server = client.servers["default"]
        path = server.test_server.server_store.export(pref.ref)
        tgz = os.path.join(path, "conan_export.tgz")
        save(tgz, "contents")  # dummy content to break it, so the download decompress will fail
        client.run("install --requires=hello/0.1", assert_error=True)
        assert "Error while extracting downloaded file" in client.out
        assert not os.path.exists(client.get_latest_ref_layout(pref.ref).export())

    def test_remove_conaninfo(self, setup):
        """
        if the conaninfo is removed, it is considered at least a broken package by the client
        """
        client, pref = setup
        server = client.servers["default"]
        path = server.test_server.server_store.package(pref)
        conaninfo = os.path.join(path, "conaninfo.txt")
        os.unlink(conaninfo)
        client.run("install --requires=hello/0.1", assert_error=True)
        assert "ERROR: Corrupted hello/0.1:da39a3ee5e6b4b0d3255bfef95601890afd80709" \
               " in 'default' remote: no conaninfo.txt" in client.out

    def test_remove_conanfile(self, setup):
        """
        if the conanfile is removed, it is considered at least a broken package by the client
        """
        client, pref = setup
        server = client.servers["default"]
        path = server.test_server.server_store.export(pref.ref)
        conanfile = os.path.join(path, "conanfile.py")
        os.unlink(conanfile)
        client.run("install --requires=hello/0.1", assert_error=True)
        assert "Corrupted hello/0.1 in 'default' remote: no conanfile.py" in client.out

    def test_remove_pkg_conanmanifest(self, setup):
        """
        if the manifest is missing the server side can say there is no package
        """
        client, pref = setup
        server = client.servers["default"]

        path = server.test_server.server_store.package(pref)
        manifest = os.path.join(path, "conanmanifest.txt")
        os.unlink(manifest)
        client.run("install --requires=hello/0.1", assert_error=True)
        assert "ERROR: Binary package not found: 'hello/0.1" in client.out

    def test_remove_recipe_conanmanifest(self, setup):
        """
        if the manifest is missing the server side can say there is no recipe
        """
        client, pref = setup
        server = client.servers["default"]

        path = server.test_server.server_store.export(pref.ref)
        manifest = os.path.join(path, "conanmanifest.txt")
        os.unlink(manifest)
        client.run("install --requires=hello/0.1", assert_error=True)
        assert "Recipe not found: 'hello/0.1" in client.out


def test_client_retries():
    server = TestServer()
    servers = {"default": server}
    client = TestClient(servers=servers, inputs=["admin", "password"])
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . --name=lib --version=1.0 --user=lasote --channel=stable")
    client.run("upload lib/1.0@lasote/stable -c -r default")

    class DownloadFilesBrokenRequester(TestRequester):
        def __init__(self, times_to_fail=1, *args, **kwargs):
            self.times_to_fail = times_to_fail
            super(DownloadFilesBrokenRequester, self).__init__(*args, **kwargs)

        def get(self, url, **kwargs):
            # conaninfo is skipped sometimes from the output, use manifest
            if "conanmanifest.txt" in url and self.times_to_fail > 0:
                self.times_to_fail = self.times_to_fail - 1
                raise ConnectionError("Fake connection error exception")
            else:
                return super(DownloadFilesBrokenRequester, self).get(url, **kwargs)

    def DownloadFilesBrokenRequesterTimesOne(*args, **kwargs):
        return DownloadFilesBrokenRequester(1, *args, **kwargs)
    client = TestClient(servers=servers, inputs=["admin", "password"],
                        requester_class=DownloadFilesBrokenRequesterTimesOne)
    client.run("install --requires=lib/1.0@lasote/stable")
    assert "WARN: network: Error downloading file" in client.out
    assert 'Fake connection error exception' in client.out
    assert 1 == str(client.out).count("Waiting 0 seconds to retry...")

    client = TestClient(servers=servers, inputs=["admin", "password"],
                        requester_class=DownloadFilesBrokenRequesterTimesOne)
    client.save_home({"global.conf": "core.download:retry_wait=1"})
    client.run("install --requires=lib/1.0@lasote/stable")
    assert 1 == str(client.out).count("Waiting 1 seconds to retry...")

    def DownloadFilesBrokenRequesterTimesTen(*args, **kwargs):
        return DownloadFilesBrokenRequester(10, *args, **kwargs)
    client = TestClient(servers=servers, inputs=["admin", "password"],
                        requester_class=DownloadFilesBrokenRequesterTimesTen)
    client.save_home({"global.conf": "core.download:retry_wait=0\n"
                                "core.download:retry=11"})
    client.run("install --requires=lib/1.0@lasote/stable")
    assert 10 == str(client.out).count("Waiting 0 seconds to retry...")


def test_forbidden_blocked_conanmanifest():
    """ this is what happens when a server blocks downloading a specific file
    """
    server = TestServer()
    servers = {"default": server}
    client = TestClient(servers=servers, inputs=["admin", "password"])
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . --name=lib --version=1.0")
    client.run("upload lib/1.0* -c -r default")

    class DownloadForbidden(TestRequester):
        def get(self, url, **kwargs):
            if "conanmanifest.txt" in url:
                r = Response()
                r._content = "Forbidden because of security!!!"
                r.status_code = 403
                return r
            else:
                return super(DownloadForbidden, self).get(url, **kwargs)

    client = TestClient(servers=servers, inputs=["admin", "password"],
                        requester_class=DownloadForbidden)
    client.run("download lib/1.0 -r=default", assert_error=True)
    assert "Forbidden because of security!!!" in client.out

    client.run("list *")
    assert "lib/1.0" not in client.out

    client.run("install --requires=lib/1.0", assert_error=True)
    assert "Forbidden because of security!!!" in client.out

    client.run("list *")
    assert "lib/1.0" not in client.out


def test_forbidden_blocked_package_conanmanifest():
    """ this is what happens when a server blocks downloading a specific file
    """
    server = TestServer()
    servers = {"default": server}
    client = TestClient(servers=servers, inputs=["admin", "password"])
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . --name=lib --version=1.0")
    client.run("upload lib/1.0* -c -r default")

    class DownloadForbidden(TestRequester):
        def get(self, url, **kwargs):
            if "packages/" in url and "conanmanifest.txt" in url:
                r = Response()
                r._content = "Forbidden because of security!!!"
                r.status_code = 403
                return r
            else:
                return super(DownloadForbidden, self).get(url, **kwargs)

    client = TestClient(servers=servers, inputs=["admin", "password"],
                        requester_class=DownloadForbidden)
    client.run("download lib/1.0 -r=default", assert_error=True)

    def check_cache():
        assert "Forbidden because of security!!!" in client.out
        client.run("list *:* --format=json")
        listjson = json.loads(client.stdout)
        revisions = listjson["Local Cache"]["lib/1.0"]["revisions"]
        packages = revisions["4d670581ccb765839f2239cc8dff8fbd"]["packages"]
        assert packages == {}  # No binaries"

    check_cache()

    client.run("install --requires=lib/1.0", assert_error=True)
    assert "Forbidden because of security!!!" in client.out
    check_cache()
