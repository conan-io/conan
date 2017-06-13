import os
import shlex
import shutil
import sys
import uuid
from collections import Counter
from io import StringIO

import requests
import six
from mock import Mock
from six.moves.urllib.parse import urlsplit, urlunsplit
from webtest.app import TestApp

from conans import __version__ as CLIENT_VERSION, tools
from conans.client.client_cache import ClientCache
from conans.client.command import Command
from conans.client.conan_api import migrate_and_get_client_cache, Conan
from conans.client.conf import MIN_SERVER_COMPATIBLE_VERSION
from conans.client.output import ConanOutput
from conans.client.remote_manager import RemoteManager
from conans.client.remote_registry import RemoteRegistry
from conans.client.rest.auth_manager import ConanApiAuthManager
from conans.client.rest.rest_client import RestApiClient
from conans.client.rest.uploader_downloader import IterableToFileAdapter
from conans.client.rest.version_checker import VersionCheckerRequester
from conans.client.store.localdb import LocalDB
from conans.client.userio import UserIO
from conans.model.version import Version
from conans.search.search import DiskSearchManager, DiskSearchAdapter
from conans.test.server.utils.server_launcher import (TESTING_REMOTE_PRIVATE_USER,
                                                      TESTING_REMOTE_PRIVATE_PASS,
                                                      TestServerLauncher)
from conans.test.utils.runner import TestRunner
from conans.test.utils.test_files import temp_folder
from conans.util.env_reader import get_env
from conans.util.files import save_files, load, save
from conans.util.log import logger


class TestingResponse(object):
    """Wraps a response from TestApp external tool
    to guarantee the presence of response.ok, response.content
    and response.status_code, as it was a requests library object.

    Is instanced by TestRequester on each request"""

    def __init__(self, test_response):
        self.test_response = test_response

    @property
    def headers(self):
        return self.test_response.headers

    @property
    def ok(self):
        return self.test_response.status_code == 200

    @property
    def content(self):
        return self.test_response.body

    @property
    def charset(self):
        return self.test_response.charset

    @charset.setter
    def charset(self, newcharset):
        self.test_response.charset = newcharset

    @property
    def text(self):
        return self.test_response.text

    def iter_content(self, chunk_size=1):  # @UnusedVariable
        return [self.content]

    @property
    def status_code(self):
        return self.test_response.status_code


class TestRequester(object):
    """Fake requests module calling server applications
    with TestApp"""

    def __init__(self, test_servers):
        self.test_servers = test_servers

    def _get_url_path(self, url):
        # Remove schema from url
        _, _, path, query, _ = urlsplit(url)
        url = urlunsplit(("", "", path, query, ""))
        return url

    def _get_wsgi_app(self, url):
        for test_server in self.test_servers.values():
            if url.startswith(test_server.fake_url):
                return test_server.app

        raise Exception("Testing error: Not remote found")

    def get(self, url, auth=None, headers=None, verify=None, stream=None):
        headers = headers or {}
        app, url = self._prepare_call(url, headers, auth)
        if app:
            response = app.get(url, headers=headers, expect_errors=True)
            return TestingResponse(response)
        else:
            return requests.get(url, headers=headers)

    def put(self, url, data, headers=None, verify=None, auth=None):
        headers = headers or {}
        app, url = self._prepare_call(url, headers, auth=auth)
        if app:
            if isinstance(data, IterableToFileAdapter):
                data_accum = b""
                for tmp in data:
                    data_accum += tmp
                data = data_accum
            response = app.put(url, data, expect_errors=True, headers=headers)
            return TestingResponse(response)
        else:
            return requests.put(url, data=data.read())

    def delete(self, url, auth, headers, verify=None):
        headers = headers or {}
        app, url = self._prepare_call(url, headers, auth)
        if app:
            response = app.delete(url, "", headers=headers, expect_errors=True)
            return TestingResponse(response)
        else:
            return requests.delete(url, headers=headers)

    def post(self, url, auth=None, headers=None, verify=None, stream=None, data=None, json=None):
        headers = headers or {}
        app, url = self._prepare_call(url, headers, auth)
        if app:
            content_type = None
            if json:
                import json as JSON
                data = JSON.dumps(json)
                content_type = "application/json"
            response = app.post(url, data, headers=headers,
                                content_type=content_type, expect_errors=True)
            return TestingResponse(response)
        else:
            requests.post(url, data=data, json=json)

    def _prepare_call(self, url, headers, auth):
        if not url.startswith("http://fake"):  # Call to S3 (or external), perform a real request
            return None, url
        app = self._get_wsgi_app(url)
        url = self._get_url_path(url)  # Remove http://server.com

        self._set_auth_headers(auth, headers)
        return app, url

    def _set_auth_headers(self, auth, headers):
        if auth:
            mock_request = Mock()
            mock_request.headers = {}
            auth(mock_request)
            headers.update(mock_request.headers)


class TestServer(object):
    from conans import __version__ as SERVER_VERSION
    from conans.server.conf import MIN_CLIENT_COMPATIBLE_VERSION

    def __init__(self, read_permissions=None,
                 write_permissions=None, users=None, plugins=None, base_path=None,
                 server_version=Version(SERVER_VERSION),
                 min_client_compatible_version=Version(MIN_CLIENT_COMPATIBLE_VERSION),
                 server_capabilities=None):
        """
             'read_permissions' and 'write_permissions' is a list of:
                 [("opencv/2.3.4@lasote/testing", "user1, user2")]

             'users':  {username: plain-text-passwd}
        """
        # Unique identifier for this server, will be used by TestRequester
        # to determine where to call. Why? remote_manager just assing an url
        # to the rest_client, so rest_client doesn't know about object instances,
        # just urls, so testing framework performs a map between fake urls and instances
        if read_permissions is None:
            read_permissions = [("*/*@*/*", "*")]
        if write_permissions is None:
            write_permissions = []
        if users is None:
            users = {"lasote": "mypass"}

        self.fake_url = "http://fake%s.com" % str(uuid.uuid4()).replace("-", "")
        min_client_ver = min_client_compatible_version
        self.test_server = TestServerLauncher(base_path, read_permissions,
                                              write_permissions, users,
                                              base_url=self.fake_url + "/v1",
                                              plugins=plugins,
                                              server_version=server_version,
                                              min_client_compatible_version=min_client_ver,
                                              server_capabilities=server_capabilities)
        self.app = TestApp(self.test_server.ra.root_app)

    @property
    def paths(self):
        return self.test_server.file_manager.paths

    def __repr__(self):
        return "TestServer @ " + self.fake_url

    def __str__(self):
        return self.fake_url


class TestBufferConanOutput(ConanOutput):

    """ wraps the normal output of the application, captures it into an stream
    and gives it operators similar to string, so it can be compared in tests
    """

    def __init__(self):
        self._buffer = StringIO()
        ConanOutput.__init__(self, self._buffer, color=False)

    def __repr__(self):
        # FIXME: I'm sure there is a better approach. Look at six docs.
        if six.PY2:
            return str(self._buffer.getvalue().encode("ascii", "ignore"))
        else:
            return self._buffer.getvalue()

    def __str__(self, *args, **kwargs):
        return self.__repr__()

    def __eq__(self, value):
        return self.__repr__() == value

    def __ne__(self, value):
        return not self.__eq__(value)

    def __contains__(self, value):
        return value in self.__repr__()


class MockedUserIO(UserIO):

    """
    Mock for testing. If get_username or get_password is requested will raise
    an exception except we have a value to return.
    """

    def __init__(self, logins, ins=sys.stdin, out=None):
        """
        logins is a dict of {remote: list(user, password)}
        will return sequentially
        """
        assert isinstance(logins, dict)
        self.logins = logins
        self.login_index = Counter()
        UserIO.__init__(self, ins, out)

    def get_username(self, remote_name):
        """Overridable for testing purpose"""
        sub_dict = self.logins[remote_name]
        index = self.login_index[remote_name]
        if len(sub_dict) - 1 < index:
            raise Exception("Bad user/password in testing framework, "
                            "provide more tuples or input the right ones")
        return sub_dict[index][0]

    def get_password(self, remote_name):
        """Overridable for testing purpose"""
        sub_dict = self.logins[remote_name]
        index = self.login_index[remote_name]
        tmp = sub_dict[index][1]
        self.login_index.update([remote_name])
        return tmp


class TestClient(object):

    """ Test wrap of the conans application to launch tests in the same way as
    in command line
    """

    def __init__(self, base_folder=None, current_folder=None,
                 servers=None, users=None, client_version=CLIENT_VERSION,
                 min_server_compatible_version=MIN_SERVER_COMPATIBLE_VERSION,
                 requester_class=None, runner=None, path_with_spaces=True):
        """
        storage_folder: Local storage path
        current_folder: Current execution folder
        servers: dict of {remote_name: TestServer}
        logins is a list of (user, password) for auto input in order
        if required==> [("lasote", "mypass"), ("other", "otherpass")]
        """
        self.all_output = ""  # For debugging purpose, append all the run outputs
        self.users = users or {"default":
                               [(TESTING_REMOTE_PRIVATE_USER, TESTING_REMOTE_PRIVATE_PASS)]}
        self.servers = servers or {}

        self.client_version = Version(str(client_version))
        self.min_server_compatible_version = Version(str(min_server_compatible_version))

        self.base_folder = base_folder or temp_folder(path_with_spaces)
        # Define storage_folder, if not, it will be read from conf file & pointed to real user home
        self.storage_folder = os.path.join(self.base_folder, ".conan", "data")
        self.client_cache = ClientCache(self.base_folder, self.storage_folder, TestBufferConanOutput())

        search_adapter = DiskSearchAdapter()
        self.search_manager = DiskSearchManager(self.client_cache, search_adapter)

        self._default_settings(get_env("CONAN_COMPILER", "gcc"),
                               get_env("CONAN_COMPILER_VERSION", "4.8"),
                               get_env("CONAN_LIBCXX", "libstdc++"))

        self.requester_class = requester_class
        self.conan_runner = runner

        self.init_dynamic_vars()

        save(self.client_cache.registry, "")
        registry = RemoteRegistry(self.client_cache.registry, TestBufferConanOutput())
        for name, server in self.servers.items():
            if isinstance(server, TestServer):
                registry.add(name, server.fake_url)
            else:
                registry.add(name, server)

        logger.debug("Client storage = %s" % self.storage_folder)
        self.current_folder = current_folder or temp_folder(path_with_spaces)

    @property
    def paths(self):
        return self.client_cache

    def _default_settings(self, compiler, compiler_version, libcxx):
        """ allows to change the default settings in the file, to change compiler, version
        """
        # Set default settings in global defined
        self.client_cache.conan_config  # For create the default file if not existing
        text = load(self.client_cache.conan_conf_path)
        # prevent TestClient instances with reused paths to write again the compiler
        if compiler != "Visual Studio":
            text = text.replace("compiler.runtime=MD", "")
        if "compiler=" not in text:
            # text = text.replace("build_type=Release", "")

            text += "\ncompiler=%s" % compiler
            text += "\ncompiler.version=%s" % compiler_version
            if compiler != "Visual Studio":
                text += "\ncompiler.libcxx=%s" % libcxx
            save(self.client_cache.conan_conf_path, text)

    @property
    def default_compiler_visual_studio(self):
        text = load(self.client_cache.conan_conf_path)
        return "compiler=Visual Studio" in text

    def _init_collaborators(self, user_io=None):

        output = TestBufferConanOutput()
        self.user_io = user_io or MockedUserIO(self.users, out=output)

        self.runner = TestRunner(output, runner=self.conan_runner)

        # Check if servers are real
        real_servers = False
        for server in self.servers.values():
            if isinstance(server, str):  # Just URI
                real_servers = True

        if real_servers:
            requester = requests
        else:
            if self.requester_class:
                requester = self.requester_class(self.servers)
            else:
                requester = TestRequester(self.servers)

        # Verify client version against remotes
        self.requester = VersionCheckerRequester(requester, self.client_version,
                                                 self.min_server_compatible_version, output)

        put_headers = self.client_cache.read_put_headers()
        self.rest_api_client = RestApiClient(output, requester=self.requester, put_headers=put_headers)
        # To store user and token
        self.localdb = LocalDB(self.client_cache.localdb)
        # Wraps RestApiClient to add authentication support (same interface)
        auth_manager = ConanApiAuthManager(self.rest_api_client, self.user_io, self.localdb)
        # Handle remote connections
        self.remote_manager = RemoteManager(self.client_cache, auth_manager, self.user_io.out)

        # Patch the globals in tools
        tools._global_requester = requests
        tools._global_output = self.user_io.out

    def init_dynamic_vars(self, user_io=None):
        # Migration system
        self.client_cache = migrate_and_get_client_cache(self.base_folder, TestBufferConanOutput(),
                                                         storage_folder=self.storage_folder)

        # Maybe something have changed with migrations
        self._init_collaborators(user_io)

    def run(self, command_line, user_io=None, ignore_error=False):
        """ run a single command as in the command line.
            If user or password is filled, user_io will be mocked to return this
            tuple if required
        """
        self.init_dynamic_vars(user_io)
        conan = Conan(self.client_cache, self.user_io, self.runner, self.remote_manager, self.search_manager)
        command = Command(conan, self.client_cache, self.user_io)
        args = shlex.split(command_line)
        current_dir = os.getcwd()
        os.chdir(self.current_folder)

        old_modules = list(sys.modules.keys())
        try:
            error = command.run(args)
        finally:
            os.chdir(current_dir)
            # Reset sys.modules to its prev state. A .copy() DOES NOT WORK
            added_modules = set(sys.modules).difference(old_modules)
            for added in added_modules:
                sys.modules.pop(added, None)

        if not ignore_error and error:
            logger.error(self.user_io.out)
            raise Exception("Command failed:\n%s" % command_line)

        self.all_output += str(self.user_io.out)
        return error

    def save(self, files, path=None, clean_first=False):
        """ helper metod, will store files in the current folder
        param files: dict{filename: filecontents}
        """
        path = path or self.current_folder
        if clean_first:
            shutil.rmtree(self.current_folder, ignore_errors=True)
        save_files(path, files)
