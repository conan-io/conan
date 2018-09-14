import os
import random
import shlex
import shutil
import sys
import threading
import uuid
from collections import Counter
from contextlib import contextmanager
from io import StringIO

import bottle
import requests
import six
import time
from mock import Mock
from six.moves.urllib.parse import urlsplit, urlunsplit
from webtest.app import TestApp

from conans import __version__ as CLIENT_VERSION, tools
from conans.client.client_cache import ClientCache
from conans.client.command import Command
from conans.client.conan_api import migrate_and_get_client_cache, Conan, get_request_timeout
from conans.client.conan_command_output import CommandOutputer
from conans.client.conf import MIN_SERVER_COMPATIBLE_VERSION
from conans.client.output import ConanOutput
from conans.client.plugin_manager import PluginManager
from conans.client.remote_registry import RemoteRegistry
from conans.client.rest.conan_requester import ConanRequester
from conans.client.rest.uploader_downloader import IterableToFileAdapter
from conans.client.tools.scm import Git
from conans.client.userio import UserIO
from conans.model.version import Version
from conans.test.server.utils.server_launcher import (TESTING_REMOTE_PRIVATE_USER,
                                                      TESTING_REMOTE_PRIVATE_PASS,
                                                      TestServerLauncher)
from conans.test.utils.runner import TestRunner
from conans.test.utils.test_files import temp_folder
from conans.tools import set_global_instances
from conans.util.env_reader import get_env
from conans.util.files import save_files, save, mkdir
from conans.util.log import logger
from conans.model.ref import ConanFileReference, PackageReference
from conans.model.manifest import FileTreeManifest
from conans.client.tools.win import get_cased_path


def inc_recipe_manifest_timestamp(client_cache, conan_ref, inc_time):
    conan_ref = ConanFileReference.loads(str(conan_ref))
    path = client_cache.export(conan_ref)
    manifest = FileTreeManifest.load(path)
    manifest.time += inc_time
    manifest.save(path)


def inc_package_manifest_timestamp(client_cache, package_ref, inc_time):
    pkg_ref = PackageReference.loads(str(package_ref))
    path = client_cache.package(pkg_ref)
    manifest = FileTreeManifest.load(path)
    manifest.time += inc_time
    manifest.save(path)


class TestingResponse(object):
    """Wraps a response from TestApp external tool
    to guarantee the presence of response.ok, response.content
    and response.status_code, as it was a requests library object.

    Is instanced by TestRequester on each request"""

    def __init__(self, test_response):
        self.test_response = test_response

    def close(self):
        pass  # Compatibility with close() method of a requests when stream=True

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

    @staticmethod
    def _get_url_path(url):
        # Remove schema from url
        _, _, path, query, _ = urlsplit(url)
        url = urlunsplit(("", "", path, query, ""))
        return url

    def _get_wsgi_app(self, url):
        for test_server in self.test_servers.values():
            if url.startswith(test_server.fake_url):
                return test_server.app

        raise Exception("Testing error: Not remote found")

    def get(self, url, **kwargs):
        app, url = self._prepare_call(url, kwargs)
        if app:
            response = app.get(url, **kwargs)
            return TestingResponse(response)
        else:
            return requests.get(url, **kwargs)

    def put(self, url, **kwargs):
        app, url = self._prepare_call(url, kwargs)
        if app:
            response = app.put(url, **kwargs)
            return TestingResponse(response)
        else:
            return requests.put(url, **kwargs)

    def delete(self, url, **kwargs):
        app, url = self._prepare_call(url, kwargs)
        if app:
            response = app.delete(url, **kwargs)
            return TestingResponse(response)
        else:
            return requests.delete(url, **kwargs)

    def post(self, url, **kwargs):
        app, url = self._prepare_call(url, kwargs)
        if app:
            response = app.post(url, **kwargs)
            return TestingResponse(response)
        else:
            requests.post(url, **kwargs)

    def _prepare_call(self, url, kwargs):
        if not url.startswith("http://fake"):  # Call to S3 (or external), perform a real request
            return None, url
        app = self._get_wsgi_app(url)
        url = self._get_url_path(url)  # Remove http://server.com

        self._set_auth_headers(kwargs)

        if app:
            kwargs["expect_errors"] = True
            kwargs.pop("stream", None)
            kwargs.pop("verify", None)
            kwargs.pop("auth", None)
            kwargs.pop("cert", None)
            kwargs.pop("timeout", None)
            if "data" in kwargs:
                if isinstance(kwargs["data"], IterableToFileAdapter):
                    data_accum = b""
                    for tmp in kwargs["data"]:
                        data_accum += tmp
                    kwargs["data"] = data_accum
                kwargs["params"] = kwargs["data"]
                del kwargs["data"]  # Parameter in test app is called "params"
            if kwargs.get("json"):
                # json is a high level parameter of requests, not a generic one
                # translate it to data and content_type
                import json
                kwargs["params"] = json.dumps(kwargs["json"])
                kwargs["content_type"] = "application/json"
            kwargs.pop("json", None)

        return app, url

    @staticmethod
    def _set_auth_headers(kwargs):
        if kwargs.get("auth"):
            mock_request = Mock()
            mock_request.headers = {}
            kwargs["auth"](mock_request)
            if "headers" not in kwargs:
                kwargs["headers"] = {}
            kwargs["headers"].update(mock_request.headers)


class TestServer(object):
    from conans import __version__ as SERVER_VERSION
    from conans.server.conf import MIN_CLIENT_COMPATIBLE_VERSION

    def __init__(self, read_permissions=None,
                 write_permissions=None, users=None, plugins=None, base_path=None,
                 server_version=Version(SERVER_VERSION),
                 min_client_compatible_version=Version(MIN_CLIENT_COMPATIBLE_VERSION),
                 server_capabilities=None, complete_urls=False):
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
        base_url = "%s/v1" % self.fake_url if complete_urls else "v1"
        self.test_server = TestServerLauncher(base_path, read_permissions,
                                              write_permissions, users,
                                              base_url=base_url,
                                              plugins=plugins,
                                              server_version=server_version,
                                              min_client_compatible_version=min_client_ver,
                                              server_capabilities=server_capabilities)
        self.app = TestApp(self.test_server.ra.root_app)

    @property
    def paths(self):
        return self.test_server.server_store

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


def create_local_git_repo(files=None, branch=None, submodules=None, folder=None):
    tmp = folder or temp_folder()
    tmp = get_cased_path(tmp)
    if files:
        save_files(tmp, files)
    git = Git(tmp)
    git.run("init .")
    git.run('config user.email "you@example.com"')
    git.run('config user.name "Your Name"')

    if branch:
        git.run("checkout -b %s" % branch)

    git.run("add .")
    git.run('commit -m  "commiting"')

    if submodules:
        for submodule in submodules:
            git.run('submodule add "%s"' % submodule)
        git.run('commit -m "add submodules"')

    return tmp.replace("\\", "/"), git.get_revision()


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
        username_env = self._get_env_username(remote_name)
        if username_env:
            return username_env

        self._raise_if_non_interactive()
        sub_dict = self.logins[remote_name]
        index = self.login_index[remote_name]
        if len(sub_dict) - 1 < index:
            raise Exception("Bad user/password in testing framework, "
                            "provide more tuples or input the right ones")
        return sub_dict[index][0]

    def get_password(self, remote_name):
        """Overridable for testing purpose"""
        password_env = self._get_env_password(remote_name)
        if password_env:
            return password_env

        self._raise_if_non_interactive()
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

        self.client_version = Version(str(client_version))
        self.min_server_compatible_version = Version(str(min_server_compatible_version))

        self.base_folder = base_folder or temp_folder(path_with_spaces)

        # Define storage_folder, if not, it will be read from conf file & pointed to real user home
        self.storage_folder = os.path.join(self.base_folder, ".conan", "data")
        self.client_cache = ClientCache(self.base_folder, self.storage_folder, TestBufferConanOutput())

        self.requester_class = requester_class
        self.conan_runner = runner

        self.update_servers(servers)
        self.init_dynamic_vars()

        logger.debug("Client storage = %s" % self.storage_folder)
        self.current_folder = current_folder or temp_folder(path_with_spaces)

    def update_servers(self, servers):
        self.servers = servers or {}
        save(self.client_cache.registry, "")
        registry = RemoteRegistry(self.client_cache.registry, TestBufferConanOutput())

        def add_server_to_registry(name, server):
            if isinstance(server, TestServer):
                registry.add(name, server.fake_url)
            else:
                registry.add(name, server)

        for name, server in self.servers.items():
            if name == "default":
                add_server_to_registry(name, server)

        for name, server in self.servers.items():
            if name != "default":
                add_server_to_registry(name, server)

    @property
    def remote_registry(self):
        return RemoteRegistry(self.client_cache.registry, TestBufferConanOutput())

    @property
    def paths(self):
        return self.client_cache

    @property
    def default_compiler_visual_studio(self):
        settings = self.client_cache.default_profile.settings
        return settings.get("compiler", None) == "Visual Studio"

    @property
    def out(self):
        return self.user_io.out

    @contextmanager
    def chdir(self, newdir):
        old_dir = self.current_folder
        if not os.path.isabs(newdir):
            newdir = os.path.join(old_dir, newdir)
        mkdir(newdir)
        self.current_folder = newdir
        try:
            yield
        finally:
            self.current_folder = old_dir

    def _init_collaborators(self, user_io=None):

        output = TestBufferConanOutput()
        self.user_io = user_io or MockedUserIO(self.users, out=output)

        self.runner = TestRunner(output, runner=self.conan_runner)

        # Check if servers are real
        real_servers = False
        for server in self.servers.values():
            if isinstance(server, str):  # Just URI
                real_servers = True

        with tools.environment_append(self.client_cache.conan_config.env_vars):
            if real_servers:
                requester = requests.Session()
            else:
                if self.requester_class:
                    requester = self.requester_class(self.servers)
                else:
                    requester = TestRequester(self.servers)

            self.requester = ConanRequester(requester, self.client_cache,
                                            get_request_timeout())

            self.plugin_manager = PluginManager(self.client_cache.plugins_path,
                                                get_env("CONAN_PLUGINS", list()),
                                                self.user_io.out)

            self.localdb, self.rest_api_client, self.remote_manager = Conan.instance_remote_manager(
                                                            self.requester, self.client_cache,
                                                            self.user_io, self.client_version,
                                                            self.min_server_compatible_version,
                                                            self.plugin_manager)
            set_global_instances(output, self.requester)

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
        with tools.environment_append(self.client_cache.conan_config.env_vars):
            # Settings preprocessor
            interactive = not get_env("CONAN_NON_INTERACTIVE", False)
            conan = Conan(self.client_cache, self.user_io, self.runner, self.remote_manager,
                          self.plugin_manager, interactive=interactive)
        outputer = CommandOutputer(self.user_io, self.client_cache)
        command = Command(conan, self.client_cache, self.user_io, outputer)
        args = shlex.split(command_line)
        current_dir = os.getcwd()
        os.chdir(self.current_folder)
        old_path = sys.path[:]
        sys.path.append(os.path.join(self.client_cache.conan_folder, "python"))
        old_modules = list(sys.modules.keys())
        try:
            error = command.run(args)
        finally:
            sys.path = old_path
            os.chdir(current_dir)
            # Reset sys.modules to its prev state. A .copy() DOES NOT WORK
            added_modules = set(sys.modules).difference(old_modules)
            for added in added_modules:
                sys.modules.pop(added, None)

        if not ignore_error and error:
            exc_message = "\n{command_header}\n{command}\n{output_header}\n{output}\n{output_footer}\n".format(
                command_header='{:-^80}'.format(" Command failed: "),
                output_header='{:-^80}'.format(" Output: "),
                output_footer='-'*80,
                command=command_line,
                output=self.user_io.out
            )
            raise Exception(exc_message)

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
        if not files:
            mkdir(self.current_folder)


class StoppableThreadBottle(threading.Thread):
    """
    Real server to test download endpoints
    """
    server = None
    port = None

    def __init__(self, host="127.0.0.1", port=None):
        self.port = port or random.randrange(8200, 8600)
        self.server = bottle.Bottle()
        super(StoppableThreadBottle, self).__init__(target=self.server.run,
                                                    kwargs={"host": host, "port": self.port})
        self.daemon = True
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def run_server(self):
        self.start()
        time.sleep(1)
