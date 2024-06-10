import json
import os
import textwrap


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
