import json
import os
import textwrap
from unittest import mock
from unittest.mock import MagicMock

import pytest

from conan import __version__
from conan.internal.model.conf import ConfDefinition
from conan.internal.rest.conan_requester import ConanRequester
from conan.test.utils.file_server import TestFileServer
from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient
from conan.internal.util.files import save


class TestAuthSourcePlugin:
    @pytest.fixture
    def setup_test_client(self):
        client = TestClient(default_server_user=True, light=True)
        file_server = TestFileServer()
        client.servers["file_server"] = file_server
        client.save_home({"global.conf": "tools.files.download:retry=0"})

        save(os.path.join(file_server.store, "myfile.txt"), "Bye, world!")

        conanfile = textwrap.dedent(f"""
           from conan import ConanFile
           from conan.tools.files import download
           class Pkg2(ConanFile):
               name = "pkg"
               version = "1.0"
               def source(self):
                   download(self, "{file_server.fake_url}/basic-auth/myfile.txt", "myfile.txt")
           """)
        client.save({"conanfile.py": conanfile})

        return client, file_server.fake_url

    def test_error_source_plugin(self, setup_test_client):
        """ Test when the plugin fails, we want a clear message and a helpful trace
        """
        c, url = setup_test_client
        auth_plugin = textwrap.dedent("""\
            def auth_source_plugin(url):
                raise Exception("Test Error")
            """)
        c.save_home({"extensions/plugins/auth_source.py": auth_plugin})
        c.run("source conanfile.py", assert_error=True)
        assert "Test Error" in c.out

    @pytest.mark.parametrize("password", ["password", "bad-password"])
    def test_auth_source_plugin_direct_credentials(self, password, setup_test_client):
        """ Test when the plugin give a correct and wrong password, we want a message about
        the success or fail in login
        """
        should_fail = password == "bad-password"
        c, url = setup_test_client
        auth_plugin = textwrap.dedent(f"""\
            def auth_source_plugin(url):
                return {json.dumps({'user': 'user', 'password': password})}
            """)
        c.save_home({"extensions/plugins/auth_source.py": auth_plugin})
        c.run("source conanfile.py", assert_error=should_fail)
        if should_fail:
            assert "AuthenticationException" in c.out
        else:
            assert os.path.exists(os.path.join(c.current_folder, "myfile.txt"))

    def test_auth_source_plugin_fallback(self, setup_test_client):
        """ Test when the plugin do not give any user or password, we want the code to continue with
        the rest of the input methods
        """
        c, url = setup_test_client
        auth_plugin = textwrap.dedent("""\
                def auth_source_plugin(url):
                    return None
                """)
        c.save_home({"extensions/plugins/auth_source.py": auth_plugin})
        source_credentials = json.dumps({"credentials": [{"url": url, "token": "password"}]})
        c.save_home({"source_credentials.json": source_credentials})
        c.run("source conanfile.py")
        # As the auth plugin is not returning any password the code is falling back to the rest of
        # the input methods in this case provided by source_credentials.json.
        assert os.path.exists(os.path.join(c.current_folder, "myfile.txt"))

    def test_source_auth_plugin_headers(self):
        auth_plugin = textwrap.dedent(f"""\
            def auth_source_plugin(url):
                return {json.dumps({'headers': {"myheader": "myvalue"}})}
            """)
        cache_folder = temp_folder()
        save(os.path.join(cache_folder, "extensions/plugins/auth_source.py"), auth_plugin)

        mock_http_requester = MagicMock()
        with mock.patch("conan.internal.rest.conan_requester.requests", mock_http_requester):
            requester = ConanRequester(ConfDefinition(), cache_folder)
            requester.get(url="aaa", source_credentials=True)
            headers = requester._http_requester.get.call_args[1]["headers"]
            assert headers["myheader"] == "myvalue"
            assert f"Conan/{__version__}" in headers["User-Agent"]

    def test_source_credentials_headers(self):
        cache_folder = temp_folder()
        source_credentials = json.dumps({"credentials": [{"url": "aaa", "token": "mytok",
                                                          "headers": {"myheader2": "myvalue2"}}]})
        save(os.path.join(cache_folder, "source_credentials.json"), source_credentials)

        mock_http_requester = MagicMock()
        with mock.patch("conan.internal.rest.conan_requester.requests", mock_http_requester):
            requester = ConanRequester(ConfDefinition(), cache_folder)
            requester.get(url="aaa", source_credentials=True)
            headers = requester._http_requester.get.call_args[1]["headers"]
            assert headers["myheader2"] == "myvalue2"
            assert f"Conan/{__version__}" in headers["User-Agent"]
