import json
import os
import platform
import sys
import textwrap
from shutil import copy
from unittest import mock

import pytest

from conan.internal.api.uploader import compress_files
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.file_server import TestFileServer
from conan.test.utils.test_files import temp_folder
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


@pytest.mark.skipif(sys.version_info.minor < 12 or platform.system() == "Windows",
                    reason="Extraction filters only Python 3.12, using symlinks (not Windows)")
def test_blocked_malicius_tgz():
    folder = temp_folder()
    f = os.path.join(folder, "myfile.txt")
    save(f, "The contents")
    s = os.path.join(folder, "mylink.txt")
    os.symlink(f, s)
    tgz_path = compress_files({f: f, s: s}, "myfiles.tgz", dest_dir=folder)
    os.remove(f)

    conan_file = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.files import get
        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"
            def source(self):
                get(self, "http://fake_url/myfiles.tgz")
            """)
    client = TestClient()
    client.save({"conanfile.py": conan_file})

    with mock.patch("conan.tools.files.files.download") as mock_download:
        def download_zip(*args, **kwargs):  # noqa
            copy(tgz_path, os.getcwd())
        mock_download.side_effect = download_zip
        client.run("create . -c tools.files.unzip:filter=data", assert_error=True)
        assert "AbsoluteLinkError" in client.out
        client.save({"conanfile.py": conan_file.format("extract_filter='fully_trusted'")})
        client.run("create . ")  # Doesn't fail now
        # user conf has precedence
        client.save({"conanfile.py": conan_file.format("extract_filter='data'")})
        client.run("create . -c tools.files.unzip:filter=fully_trusted")  # Doesn't fail now
