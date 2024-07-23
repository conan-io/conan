import json
import os
import textwrap
from unittest import mock

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.file_server import TestFileServer
from conan.test.utils.tools import TestClient
from conans.util.files import save


def test_source_download_password():
    c = TestClient()
    file_server = TestFileServer()
    c.servers["file_server"] = file_server
    save(os.path.join(file_server.store, "myfile.txt"), "hello world!")

    server_url = file_server.fake_url

    conanfile = textwrap.dedent(f"""
        from conan import ConanFile
        from conan.tools.files import download, load
        class Pkg(ConanFile):
            def source(self):
                download(self, "{server_url}/basic-auth/myfile.txt", "myfile.txt")
                self.output.info(f"Content: {{load(self, 'myfile.txt')}}")
            """)
    c.save({"conanfile.py": conanfile})
    content = {"credentials": [{"url": server_url, "token": "password"}]}
    save(os.path.join(c.cache_folder, "source_credentials.json"), json.dumps(content))
    c.run("source .")
    assert "Content: hello world!" in c.out
    content = {"credentials": [{"url": server_url,
                                "user": "user", "password": "password"}]}
    save(os.path.join(c.cache_folder, "source_credentials.json"), json.dumps(content))
    c.run("source .")
    assert "Content: hello world!" in c.out

    content = {"credentials": [{"url": server_url, "token": "{{mytk}}"}]}
    content = "{% set mytk = 'password' %}\n" + json.dumps(content)
    save(os.path.join(c.cache_folder, "source_credentials.json"), content)
    c.run("source .")
    assert "Content: hello world!" in c.out

    # Errors loading file
    for invalid in ["",
                    "potato",
                    {"token": "mytoken"},
                    {},
                    {"url": server_url},
                    {"auth": {}},
                    {"user": "other", "password": "pass"}]:
        content = {"credentials": [invalid]}
        save(os.path.join(c.cache_folder, "source_credentials.json"), json.dumps(content))
        c.run("source .", assert_error=True)
        assert "Error loading 'source_credentials.json'" in c.out

    content = {"credentials": [{"url": server_url, "token": "mytoken2"}]}
    save(os.path.join(c.cache_folder, "source_credentials.json"), json.dumps(content))
    c.run("source .", assert_error=True)
    assert "ERROR: conanfile.py: Error in source() method, line 6" in c.out
    assert "Authentication" in c.out


def test_source_credentials_only_download():
    # https://github.com/conan-io/conan/issues/16396
    c = TestClient(default_server_user=True)
    url = c.servers["default"].fake_url

    content = {"credentials": [{"url": url, "token": "password stpaces"}]}
    save(os.path.join(c.cache_folder, "source_credentials.json"), json.dumps(content))

    c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
    c.run("create .")
    # add_auth should never be called for regular upload/download
    with mock.patch("conans.client.rest.conan_requester._SourceURLCredentials.add_auth", None):
        c.run("upload * -c -r=default")
        c.run("remove * -c")
        c.run("download pkg/0.1 -r=default")
