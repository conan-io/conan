import json
import os
import pytest
from collections import OrderedDict

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient, TestServer
from conan.internal.util.files import load


class TestRemoteServer:

    @pytest.fixture(autouse=True)
    def setup(self):
        self.servers = OrderedDict()
        for i in range(3):
            test_server = TestServer()
            self.servers["remote%d" % i] = test_server

        self.client = TestClient(servers=self.servers, inputs=3 * ["admin", "password"], light=True)

    def test_list_json(self):
        self.client.run("remote list --format=json")
        data = json.loads(self.client.stdout)

        assert data[0]["name"] == "remote0"
        assert data[1]["name"] == "remote1"
        assert data[2]["name"] == "remote2"
        # TODO: Check better

    def test_basic(self):
        self.client.run("remote list")
        assert "remote0: http://" in self.client.out
        assert "remote1: http://" in self.client.out
        assert "remote2: http://" in self.client.out

        self.client.run("remote add origin https://myurl")
        self.client.run("remote list")
        lines = str(self.client.out).splitlines()
        assert "origin: https://myurl" in lines[3]

        self.client.run("remote update origin --url https://2myurl")
        self.client.run("remote list")
        assert "origin: https://2myurl" in self.client.out

        self.client.run("remote update remote0 --url https://remote0url")
        self.client.run("remote list")
        output = str(self.client.out)
        assert "remote0: https://remote0url" in output.splitlines()[0]

        self.client.run("remote remove remote0")
        self.client.run("remote list")
        output = str(self.client.out)
        assert "remote1: http://" in output.splitlines()[0]

    def test_remove_remote(self):
        self.client.run("remote list")
        assert "remote0: http://" in self.client.out
        assert "remote1: http://" in self.client.out
        assert "remote2: http://" in self.client.out
        self.client.run("remote remove remote1")
        self.client.run("remote list")
        assert "remote1" not in self.client.out
        assert "remote0" in self.client.out
        assert "remote2" in self.client.out
        self.client.run("remote remove remote2")
        self.client.run("remote list")
        assert "remote1" not in self.client.out
        assert "remote0" in self.client.out
        assert "remote2" not in self.client.out

    def test_remove_remote_all(self):
        self.client.run("remote list")
        assert "remote0: http://" in self.client.out
        assert "remote1: http://" in self.client.out
        assert "remote2: http://" in self.client.out
        self.client.run("remote remove *")
        self.client.run("remote list")
        assert "remote1" not in self.client.out
        assert "remote0" not in self.client.out
        assert "remote2" not in self.client.out

    def test_remove_remote_no_user(self):
        self.client.save({"conanfile.py": GenConanfile()})
        self.client.run("remote remove remote0")
        self.client.run("remote list")
        assert "remote0" not in self.client.out

    def test_insert(self):
        self.client.run("remote add origin https://myurl --index", assert_error=True)

        self.client.run("remote add origin https://myurl --index=0")
        self.client.run("remote add origin2 https://myurl2 --index=0")
        self.client.run("remote list")
        lines = str(self.client.out).splitlines()
        assert "origin2: https://myurl2" in lines[0]
        assert "origin: https://myurl" in lines[1]

        self.client.run("remote add origin3 https://myurl3 --index=1")
        self.client.run("remote list")
        lines = str(self.client.out).splitlines()
        assert "origin2: https://myurl2" in lines[0]
        assert "origin3: https://myurl3" in lines[1]
        assert "origin: https://myurl" in lines[2]

    def test_duplicated_error(self):
        """ check remote name are not duplicated
        """
        self.client.run("remote add remote1 http://otherurl", assert_error=True)
        assert "ERROR: Remote 'remote1' already exists in remotes (use --force to continue)" \
                      in self.client.out

        self.client.run("remote list")
        assert "otherurl" not in self.client.out
        self.client.run("remote add remote1 http://otherurl --force")
        assert "WARN: Remote 'remote1' already exists in remotes" in self.client.out

        self.client.run("remote list")
        assert "remote1: http://otherurl" in self.client.out

    def test_missing_subarguments(self):
        self.client.run("remote", assert_error=True)
        assert "ERROR: Exiting with code: 2" in self.client.out

    def test_invalid_url(self):
        self.client.run("remote add foobar foobar.com")
        assert "WARN: The URL 'foobar.com' is invalid. It must contain scheme and hostname." \
                      in self.client.out
        self.client.run("remote list")
        assert "foobar.com" in self.client.out

        self.client.run("remote update foobar --url pepe.org")
        assert "WARN: The URL 'pepe.org' is invalid. It must contain scheme and hostname." \
                      in self.client.out
        self.client.run("remote list")
        assert "pepe.org" in self.client.out

    def test_errors(self):
        self.client.run("remote update origin --url http://foo.com", assert_error=True)
        assert "ERROR: Remote 'origin' doesn't exist" in self.client.out

        self.client.run("remote remove origin", assert_error=True)
        assert "ERROR: Remote 'origin' can't be found or is disabled" in self.client.out


class TestRemoteModification:
    def test_rename(self):
        client = TestClient(light=True)
        client.save({"conanfile.py": GenConanfile()})
        client.run("export . --name=hello --version=0.1 --user=user --channel=testing")
        client.run("remote add r1 https://r1")
        client.run("remote add r2 https://r2")
        client.run("remote add r3 https://r3")
        client.run("remote rename r2 mynewr2")
        client.run("remote list")
        lines = str(client.out).splitlines()
        assert "r1: https://r1" in lines[0]
        assert "mynewr2: https://r2" in lines[1]
        assert "r3: https://r3" in lines[2]

        # Rename to an existing one
        client.run("remote rename mynewr2 r1", assert_error=True)
        assert "Remote 'r1' already exists" in client.out

    def test_update_insert(self):
        client = TestClient(light=True)
        client.run("remote add r1 https://r1")
        client.run("remote add r2 https://r2")
        client.run("remote add r3 https://r3")

        client.run("remote update r2 --url https://r2new --index=0")
        client.run("remote list")
        lines = str(client.out).splitlines()
        assert "r2: https://r2new" in lines[0]
        assert "r1: https://r1" in lines[1]
        assert "r3: https://r3" in lines[2]

        client.run("remote update r2 --url https://r2new2")
        client.run("remote update r2 --index=2")
        client.run("remote list")
        lines = str(client.out).splitlines()
        assert "r1: https://r1" in lines[0]
        assert "r3: https://r3" in lines[1]
        assert "r2: https://r2new2" in lines[2]

    def test_update_insert_same_url(self):
        # https://github.com/conan-io/conan/issues/5107
        client = TestClient(light=True)
        client.run("remote add r1 https://r1")
        client.run("remote add r2 https://r2")
        client.run("remote add r3 https://r3")
        client.run("remote update r2 --url https://r2")
        client.run("remote update r2 --index 0")
        client.run("remote list")
        assert str(client.out).find("r2") < str(client.out).find("r1")
        assert str(client.out).find("r1") < str(client.out).find("r3")

    def test_verify_ssl(self):
        client = TestClient(light=True)
        client.run("remote add my-remote http://someurl")
        client.run("remote add my-remote2 http://someurl2 --insecure")
        client.run("remote add my-remote3 http://someurl3")

        registry = load(client.paths.remotes_path)
        data = json.loads(registry)
        assert data["remotes"][0]["name"] == "my-remote"
        assert data["remotes"][0]["url"] == "http://someurl"
        assert data["remotes"][0]["verify_ssl"] == True

        assert data["remotes"][1]["name"] == "my-remote2"
        assert data["remotes"][1]["url"] == "http://someurl2"
        assert data["remotes"][1]["verify_ssl"] == False

        assert data["remotes"][2]["name"] == "my-remote3"
        assert data["remotes"][2]["url"] == "http://someurl3"
        assert data["remotes"][2]["verify_ssl"] == True

    def test_remote_disable(self):
        client = TestClient(light=True)
        client.run("remote add my-remote0 http://someurl0")
        client.run("remote add my-remote1 http://someurl1")
        client.run("remote add my-remote2 http://someurl2")
        client.run("remote add my-remote3 http://someurl3")
        client.run("remote disable my-remote0")
        assert "my-remote0" in client.out
        assert "Enabled: False" in client.out
        client.run("remote disable my-remote3")
        assert "my-remote3" in client.out
        assert "Enabled: False" in client.out
        registry = load(client.paths.remotes_path)
        data = json.loads(registry)
        assert data["remotes"][0]["name"] == "my-remote0"
        assert data["remotes"][0]["url"] == "http://someurl0"
        assert data["remotes"][0]["disabled"] == True
        assert data["remotes"][3]["name"] == "my-remote3"
        assert data["remotes"][3]["url"] == "http://someurl3"
        assert data["remotes"][3]["disabled"] == True

        # check that they are still listed, as disabled
        client.run("remote list")
        assert "my-remote0: http://someurl0 [Verify SSL: True, Enabled: False]" in client.out
        assert "my-remote3: http://someurl3 [Verify SSL: True, Enabled: False]" in client.out

        client.run("remote disable * --format=json")

        registry = load(client.paths.remotes_path)
        data = json.loads(registry)
        for remote in data["remotes"]:
            assert remote["disabled"] == True

        data = json.loads(client.stdout)
        for remote in data:
            assert remote["enabled"] is False

        client.run("remote enable *")
        registry = load(client.paths.remotes_path)
        data = json.loads(registry)
        for remote in data["remotes"]:
            assert "disabled" not in remote
        assert "my-remote0" in client.out
        assert "my-remote1" in client.out
        assert "my-remote2" in client.out
        assert "my-remote3" in client.out
        assert "Enabled: False" not in client.out

    def test_invalid_remote_disable(self):
        client = TestClient(light=True)

        client.run("remote disable invalid_remote", assert_error=True)
        msg = "ERROR: Remote 'invalid_remote' can't be found or is disabled"
        assert msg in client.out

        client.run("remote enable invalid_remote", assert_error=True)
        assert msg in client.out

        client.run("remote disable invalid_wildcard_*")

    def test_remote_disable_already_set(self):
        """
        Check that we don't raise an error if the remote is already in the required state
        """
        client = TestClient(light=True)

        client.run("remote add my-remote0 http://someurl0")
        client.run("remote enable my-remote0")
        client.run("remote enable my-remote0")

        client.run("remote disable my-remote0")
        client.run("remote disable my-remote0")

    def test_verify_ssl_error(self):
        client = TestClient(light=True)
        client.run("remote add my-remote http://someurl some_invalid_option=foo", assert_error=True)

        assert "unrecognized arguments: some_invalid_option=foo" in client.out
        data = json.loads(load(client.paths.remotes_path))
        assert data["remotes"] == []


def test_add_duplicated_url():
    """ allow duplicated URL with --force
    """
    c = TestClient(light=True)
    c.run("remote add remote1 http://url")
    c.run("remote add remote2 http://url", assert_error=True)
    assert "ERROR: Remote url already existing in remote 'remote1'" in c.out
    c.run("remote list")
    assert "remote1" in c.out
    assert "remote2" not in c.out
    c.run("remote add remote2 http://url --force")
    assert "WARN: Remote url already existing in remote 'remote1'." in c.out
    c.run("remote list")
    assert "remote1" in c.out
    assert "remote2" in c.out
    # make sure we can remove both
    # https://github.com/conan-io/conan/issues/13569
    c.run("remote remove *")
    c.run("remote list")
    assert "remote1" not in c.out
    assert "remote2" not in c.out


def test_add_duplicated_name_url():
    """ do not add extra remote with same name and same url
        # https://github.com/conan-io/conan/issues/13569
    """
    c = TestClient(light=True)
    c.run("remote add remote1 http://url")
    c.run("remote add remote1 http://url --force")
    assert "WARN: Remote 'remote1' already exists in remotes" in c.out
    c.run("remote list")
    assert 1 == str(c.out).count("remote1")


def test_add_wrong_conancenter():
    """ Avoid common error of adding the wrong ConanCenter URL
    """
    c = TestClient(light=True)
    c.run("remote add whatever https://conan.io/center", assert_error=True)
    assert "Wrong ConanCenter remote URL. You are adding the web https://conan.io/center" in c.out
    assert "the correct remote API is https://center2.conan.io" in c.out
    c.run("remote add conancenter https://center2.conan.io")
    c.run("remote update conancenter --url=https://conan.io/center", assert_error=True)
    assert "Wrong ConanCenter remote URL. You are adding the web https://conan.io/center" in c.out
    assert "the correct remote API is https://center2.conan.io" in c.out


def test_using_frozen_center():
    """ If the legacy center.conan.io is in the remote list warn about it.
    """
    c = TestClient(light=True)
    c.run("remote add whatever https://center.conan.io")
    assert "The remote 'https://center.conan.io' is now frozen and has been replaced by 'https://center2.conan.io'." in c.out
    assert 'conan remote update whatever --url="https://center2.conan.io"' in c.out

    c.run("remote list")
    assert "The remote 'https://center.conan.io' is now frozen and has been replaced by 'https://center2.conan.io'." in c.out

    c.run("remote remove whatever")

    c.run("remote add conancenter https://center2.conan.io")
    assert "The remote 'https://center.conan.io' is now frozen and has been replaced by 'https://center2.conan.io'." not in c.out

    c.run("remote list")
    assert "The remote 'https://center.conan.io' is now frozen and has been replaced by 'https://center2.conan.io'." not in c.out

    c.run("remote update conancenter --url=https://center.conan.io")
    assert "The remote 'https://center.conan.io' is now frozen and has been replaced by 'https://center2.conan.io'." in c.out

    c.run("remote disable conancenter")
    assert "The remote 'https://center.conan.io' is now frozen and has been replaced by 'https://center2.conan.io'." not in c.out


def test_wrong_remotes_json_file():
    c = TestClient(light=True)
    c.save_home({"remotes.json": ""})
    c.run("remote list", assert_error=True)
    assert "ERROR: Error loading JSON remotes file" in c.out


def test_allowed_packages_remotes():
    tc = TestClient(light=True, default_server_user=True)
    tc.save({"conanfile.py": GenConanfile(),
             "app/conanfile.py": GenConanfile("app", "1.0")
            .with_requires("liba/1.0")
            .with_requires("libb/[>=1.0]")})
    tc.run("create . --name=liba --version=1.0")
    tc.run("create . --name=libb --version=1.0")
    tc.run("create app")
    tc.run("upload * -r=default -c")
    tc.run("remove * -c")

    tc.run("install --requires=app/1.0 -r=default")
    assert "app/1.0: Downloaded recipe revision 04ab3bc4b945a2ee44285962c277906d" in tc.out
    assert "liba/1.0: Downloaded recipe revision 4d670581ccb765839f2239cc8dff8fbd" in tc.out
    tc.run("remove * -c")

    # lib/2.* pattern does not match the one being required by app, should not be found
    tc.run('remote update default --allowed-packages="app/*" --allowed-packages="liba/2.*"')

    tc.run("install --requires=app/1.0 -r=default", assert_error=True)
    assert "app/1.0: Downloaded recipe revision 04ab3bc4b945a2ee44285962c277906d" in tc.out
    assert "liba/1.0: Downloaded recipe revision 4d670581ccb765839f2239cc8dff8fbd" not in tc.out
    assert "ERROR: Package 'liba/1.0' not resolved: Unable to find 'liba/1.0' in remotes" in tc.out
    tc.run("remove * -c")

    tc.run('remote update default --allowed-packages="liba/*" --allowed-packages="app/*"')
    tc.run("remote list -f=json")
    assert "app/*" in tc.out

    tc.run("install --requires=app/1.0 -r=default", assert_error=True)
    assert "app/1.0: Downloaded recipe revision 04ab3bc4b945a2ee44285962c277906d" in tc.out
    assert "liba/1.0: Downloaded recipe revision 4d670581ccb765839f2239cc8dff8fbd" in tc.out
    assert "ERROR: Package 'libb/[>=1.0]' not resolved" in tc.out
    tc.run("remove * -c")

    tc.run('remote update default --allowed-packages="liba/*" --allowed-packages="app/*"')
    tc.run("install --requires=app/1.0 -r=default", assert_error=True)
    assert "app/1.0: Downloaded recipe revision 04ab3bc4b945a2ee44285962c277906d" in tc.out
    assert "liba/1.0: Downloaded recipe revision 4d670581ccb765839f2239cc8dff8fbd" in tc.out
    assert "ERROR: Package 'libb/[>=1.0]' not resolved" in tc.out
    tc.run("remove * -c")

    tc.run('remote update default --allowed-packages="*"')
    tc.run("install --requires=app/1.0 -r=default")
    assert "app/1.0: Downloaded recipe revision 04ab3bc4b945a2ee44285962c277906d" in tc.out
    assert "liba/1.0: Downloaded recipe revision 4d670581ccb765839f2239cc8dff8fbd" in tc.out
    assert "libb/1.0: Downloaded recipe revision 4d670581ccb765839f2239cc8dff8fbd" in tc.out


def test_remote_allowed_packages_new():
    """Test that the allowed packages are saved in the remotes.json file when adding a new remote"""
    tc = TestClient(light=True)
    tc.run("remote add foo https://foo -ap='liba/*'")
    remotes = json.loads(load(os.path.join(tc.cache_folder, "remotes.json")))
    assert remotes["remotes"][0]["allowed_packages"] == ["liba/*"]


def test_remote_allowed_negation():
    tc = TestClient(light=True, default_server_user=True)
    tc.save({"conanfile.py": GenConanfile()})
    tc.run("create . --name=config --version=1.0")
    tc.run("create . --name=lib --version=1.0")
    tc.run("upload * -c -r=default")
    tc.run("remove * -c")

    tc.run('remote update default --allowed-packages="!config/*"')
    tc.run("install --requires=lib/1.0 -r=default")
    assert "lib/1.0: Downloaded recipe revision" in tc.out

    tc.run("install --requires=config/1.0 -r=default", assert_error=True)
    assert "ERROR: Package 'config/1.0' not resolved: Unable to find 'config/1.0' in remotes" in tc.out
