import base64
import json
import os
import textwrap

from bottle import static_file, request, HTTPError

from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient, StoppableThreadBottle
from conans.util.files import save


def test_source_download_password():
    http_server = StoppableThreadBottle()
    http_server_base_folder = temp_folder()
    save(os.path.join(http_server_base_folder, "myfile.txt"), "hello world!")

    def valid_auth():
        auth = request.headers.get("Authorization")
        if auth == "Bearer mytoken":
            return
        if auth and "Basic" in auth and \
                base64.b64decode(auth[6:], validate=False) == b"myuser:mypassword":
            return
        return HTTPError(401, "Authentication required")

    @http_server.server.get("/<file>")
    def get_file(file):
        ret = valid_auth()
        return ret or static_file(file, http_server_base_folder)

    @http_server.server.put("/<file>")
    def put_file(file):
        ret = valid_auth()
        if ret:
            return ret
        dest = os.path.join(http_server_base_folder, file)
        with open(dest, 'wb') as f:
            f.write(request.body.read())

    http_server.run_server()

    c = TestClient()
    conanfile = textwrap.dedent(f"""
        from conan import ConanFile
        from conan.tools.files import download, load
        class Pkg(ConanFile):
            def source(self):
                download(self, "http://localhost:{http_server.port}/myfile.txt", "myfile.txt")
                self.output.info(f"Content: {{load(self, 'myfile.txt')}}")
            """)
    c.save({"conanfile.py": conanfile})
    content = {f"http://localhost:{http_server.port}": {"token": "mytoken"}}
    save(os.path.join(c.cache_folder, "source_credentials.json"), json.dumps(content))
    c.run("source .")
    assert "Content: hello world!" in c.out
    content = {f"http://localhost:{http_server.port}": {
        "auth": {"user": "myuser", "password": "mypassword"}}
    }
    save(os.path.join(c.cache_folder, "source_credentials.json"), json.dumps(content))
    c.run("source .")
    assert "Content: hello world!" in c.out

    content = {f"http://localhost:{http_server.port}": {"token": "{{mytk}}"}}
    content = "{% set mytk = 'mytoken' %}\n" + json.dumps(content)
    save(os.path.join(c.cache_folder, "source_credentials.json"), content)
    c.run("source .")
    assert "Content: hello world!" in c.out

    # Errors
    for invalid in [{"token": "mytoken2"},
                    {},
                    {"auth": {}},
                    {"auth": {"user": "other", "password": "pass"}}]:
        content = {f"http://localhost:{http_server.port}": invalid}
        save(os.path.join(c.cache_folder, "source_credentials.json"), json.dumps(content))
        c.run("source .", assert_error=True)
        assert "Authentication" in c.out
