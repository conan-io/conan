import json
import os

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient, TestServer
from conans.util.files import save


def test_remote_file_credentials():
    test_server = TestServer()
    c = TestClient(servers={"default": test_server},)
    c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
    c.run("create .")
    c.run("upload * -r=default -c", assert_error=True)
    content = {"credentials": [{"remote": "default", "user": "admin", "password": "password"}]}
    save(os.path.join(c.cache_folder, "credentials.json"), json.dumps(content))
    c.run("upload * -r=default -c")
