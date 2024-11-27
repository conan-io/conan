import json
import os

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient, TestServer
from conans.util.files import save


@pytest.fixture()
def client():
    test_server = TestServer()
    c = TestClient(servers={"default": test_server})
    c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
    c.run("create .")
    c.run("upload * -r=default -c", assert_error=True)
    return c


def test_remote_file_credentials(client):
    c = client
    content = {"credentials": [{"remote": "default", "user": "admin", "password": "password"}]}
    save(os.path.join(c.cache_folder, "credentials.json"), json.dumps(content))
    c.run("upload * -r=default -c")
    # it works without problems!
    assert "Uploading recipe" in c.out


def test_remote_file_credentials_remote_login(client):
    c = client
    content = {"credentials": [{"remote": "default", "user": "admin", "password": "password"}]}
    save(os.path.join(c.cache_folder, "credentials.json"), json.dumps(content))
    c.run("remote login default")
    assert "Changed user of remote 'default' from 'None' (anonymous) " \
           "to 'admin' (authenticated)" in c.out


def test_remote_file_credentials_error(client):
    c = client
    content = {"credentials": [{"remote": "default", "user": "admin", "password": "wrong"}]}
    save(os.path.join(c.cache_folder, "credentials.json"), json.dumps(content))
    c.run("upload * -r=default -c", assert_error=True)
    assert "ERROR: Wrong user or password" in c.out


def test_remote_file_credentials_bad_file(client):
    c = client
    save(os.path.join(c.cache_folder, "credentials.json"), "")
    c.run("upload * -r=default -c", assert_error=True)
    assert "ERROR: Error loading 'credentials.json'" in c.out
    content = {"credentials": [{"remote": "default"}]}
    save(os.path.join(c.cache_folder, "credentials.json"), json.dumps(content))
    c.run("upload * -r=default -c", assert_error=True)
    assert "ERROR: Error loading 'credentials.json'" in c.out
