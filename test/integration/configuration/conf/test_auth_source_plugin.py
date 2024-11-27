import json
import os
import textwrap

import pytest

from conan.test.utils.file_server import TestFileServer
from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient
from conans.util.files import save


class TestAuthSourcePlugin:
    @pytest.fixture
    def setup_test_client(self):
        self.client = TestClient(default_server_user=True, light=True)
        self.file_server = TestFileServer()
        self.client.servers["file_server"] = self.file_server
        self.download_cache_folder = temp_folder()
        self.client.save_home({"global.conf": "tools.files.download:retry=0"})

        save(os.path.join(self.file_server.store, "myfile.txt"), "Bye, world!")

        conanfile = textwrap.dedent(f"""
                           from conan import ConanFile
                           from conan.tools.files import download
                           class Pkg2(ConanFile):
                               name = "pkg"
                               version = "1.0"
                               def source(self):
                                   download(self, "{self.file_server.fake_url}/basic-auth/myfile.txt", "myfile.txt")
                           """)
        self.client.save({"conanfile.py": conanfile})

        return self.client, self.file_server.fake_url

    """ Test when the plugin fails, we want a clear message and a helpful trace
    """
    def test_error_source_plugin(self, setup_test_client):
        c, url = setup_test_client
        auth_plugin = textwrap.dedent("""\
            def auth_source_plugin(url):
                raise Exception("Test Error")
            """)
        save(os.path.join(c.cache.plugins_path, "auth_source.py"), auth_plugin)
        c.run("source conanfile.py", assert_error=True)
        assert "Test Error" in c.out

    """ Test when the plugin give a correct and wrong password, we want a message about the success
        or fail in login
    """
    @pytest.mark.parametrize("password", ["password", "bad-password"])
    def test_auth_source_plugin_direct_credentials(self, password, setup_test_client):
        should_fail = password == "bad-password"
        c, url = setup_test_client
        auth_plugin = textwrap.dedent(f"""\
            def auth_source_plugin(url):
                return { json.dumps({'user': 'user', 'password': password}) }
            """)
        save(os.path.join(c.cache.plugins_path, "auth_source.py"), auth_plugin)
        c.run("source conanfile.py", assert_error=should_fail)
        if should_fail:
            assert "AuthenticationException" in c.out
        else:
            assert os.path.exists(os.path.join(c.current_folder, "myfile.txt"))

    """ Test when the plugin do not give any user or password, we want the code to continue with
        the rest of the input methods
    """
    def test_auth_source_plugin_fallback(self, setup_test_client):
        c, url = setup_test_client
        auth_plugin = textwrap.dedent("""\
                def auth_source_plugin(url):
                    return None
                """)
        save(os.path.join(c.cache.plugins_path, "auth_source.py"), auth_plugin)
        source_credentials = json.dumps({"credentials": [{"url": url, "token": "password"}]})
        save(os.path.join(c.cache_folder, "source_credentials.json"), source_credentials)
        c.run("source conanfile.py")
        # As the auth plugin is not returning any password the code is falling back to the rest of
        # the input methods in this case provided by source_credentials.json.
        assert os.path.exists(os.path.join(c.current_folder, "myfile.txt"))
