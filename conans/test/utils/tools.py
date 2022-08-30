import json
import os
import shlex
import shutil
import socket
import sys
import textwrap
import threading
import time
import uuid
import zipfile
from collections import OrderedDict
from contextlib import contextmanager

import bottle
import requests
from mock import Mock
from requests.exceptions import HTTPError
from six.moves.urllib.parse import urlsplit, urlunsplit
from webtest.app import TestApp

from conans import load
from conans.cli.cli import Cli
from conans.client.api.conan_api import ConanAPIV2
from conans.client.cache.cache import ClientCache
from conans.client.cache.remote_registry import Remotes
from conans.client.command import Command
from conans.client.conan_api import Conan
from conans.client.rest.file_uploader import IterableToFileAdapter
from conans.client.runner import ConanRunner
from conans.client.tools import environment_append
from conans.client.tools.files import replace_in_file
from conans.errors import NotFoundException
from conans.model.manifest import FileTreeManifest
from conans.model.profile import Profile
from conans.model.ref import ConanFileReference, PackageReference
from conans.model.settings import Settings
from conans.test.assets import copy_assets
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.artifactory import ARTIFACTORY_DEFAULT_USER, ARTIFACTORY_DEFAULT_PASSWORD, \
    ArtifactoryServer
from conans.test.utils.mocks import MockedUserIO, TestBufferConanOutput, RedirectedTestOutput
from conans.test.utils.scm import create_local_git_repo, create_local_svn_checkout, \
    create_remote_svn_repo
from conans.test.utils.server_launcher import (TESTING_REMOTE_PRIVATE_PASS,
                                               TESTING_REMOTE_PRIVATE_USER,
                                               TestServerLauncher)
from conans.test.utils.test_files import temp_folder
from conans.util.conan_v2_mode import CONAN_V2_MODE_ENVVAR
from conans.util.env_reader import get_env
from conans.util.files import mkdir, save_files

NO_SETTINGS_PACKAGE_ID = "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9"


def inc_recipe_manifest_timestamp(cache, reference, inc_time):
    ref = ConanFileReference.loads(reference)
    path = cache.package_layout(ref).export()
    manifest = FileTreeManifest.load(path)
    manifest.time += inc_time
    manifest.save(path)


def inc_package_manifest_timestamp(cache, package_reference, inc_time):
    pref = PackageReference.loads(package_reference)
    path = cache.package_layout(pref.ref).package(pref)
    manifest = FileTreeManifest.load(path)
    manifest.time += inc_time
    manifest.save(path)


def create_profile(profile=None, settings=None):
    if profile is None:
        profile = Profile()
    if profile.processed_settings is None:
        profile.processed_settings = settings or Settings()
    return profile


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

    def raise_for_status(self):
        """Raises stored :class:`HTTPError`, if one occurred."""
        http_error_msg = ''
        if 400 <= self.status_code < 500:
            http_error_msg = u'%s Client Error: %s' % (self.status_code, self.content)

        elif 500 <= self.status_code < 600:
            http_error_msg = u'%s Server Error: %s' % (self.status_code, self.content)

        if http_error_msg:
            raise HTTPError(http_error_msg, response=self)

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

    def json(self):
        try:
            return json.loads(self.test_response.content)
        except:
            raise ValueError("The response is not a JSON")


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
    def __init__(self, read_permissions=None,
                 write_permissions=None, users=None, plugins=None, base_path=None,
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
            users = {"lasote": "mypass", "conan": "password"}

        self.fake_url = "http://fake%s.com" % str(uuid.uuid4()).replace("-", "")
        base_url = "%s/v1" % self.fake_url if complete_urls else "v1"
        self.test_server = TestServerLauncher(base_path, read_permissions,
                                              write_permissions, users,
                                              base_url=base_url,
                                              plugins=plugins,
                                              server_capabilities=server_capabilities)
        self.app = TestApp(self.test_server.ra.root_app)

    @property
    def server_store(self):
        return self.test_server.server_store

    def __repr__(self):
        return "TestServer @ " + self.fake_url

    def __str__(self):
        return self.fake_url

    def recipe_exists(self, ref):
        try:
            if not ref.revision:
                path = self.test_server.server_store.conan_revisions_root(ref)
            else:
                path = self.test_server.server_store.base_folder(ref)
            return self.test_server.server_store.path_exists(path)
        except NotFoundException:  # When resolves the latest and there is no package
            return False

    def package_exists(self, pref):
        try:
            if pref.revision:
                path = self.test_server.server_store.package(pref)
            else:
                path = self.test_server.server_store.package_revisions_root(pref)
            return self.test_server.server_store.path_exists(path)
        except NotFoundException:  # When resolves the latest and there is no package
            return False

    def latest_recipe(self, ref):
        rev, _ = self.test_server.server_store.get_last_revision(ref)
        return ref.copy_with_rev(rev)

    def recipe_revision_time(self, ref):
        if not ref.revision:
            raise Exception("Pass a ref with revision (Testing framework)")
        return self.test_server.server_store.get_revision_time(ref)

    def latest_package(self, pref):
        if not pref.ref.revision:
            raise Exception("Pass a pref with .rev.revision (Testing framework)")
        prev = self.test_server.server_store.get_last_package_revision(pref)
        return pref.copy_with_revs(pref.ref.revision, prev)

    def package_revision_time(self, pref):
        if not pref:
            raise Exception("Pass a pref with revision (Testing framework)")
        tmp = self.test_server.server_store.get_package_revision_time(pref)
        return tmp


if get_env("CONAN_TEST_WITH_ARTIFACTORY", False):
    TestServer = ArtifactoryServer


def _copy_cache_folder(target_folder):
    # Some variables affect to cache population (take a different default folder)
    vars_ = [CONAN_V2_MODE_ENVVAR, 'CC', 'CXX', 'PATH']
    cache_key = hash('|'.join(map(str, [os.environ.get(it, None) for it in vars_])))
    master_folder = _copy_cache_folder.master.setdefault(cache_key, temp_folder(create_dir=False))
    if not os.path.exists(master_folder):
        # Create and populate the cache folder with the defaults
        cache = ClientCache(master_folder, TestBufferConanOutput())
        cache.initialize_config()
        cache.registry.initialize_remotes()
        cache.initialize_default_profile()
        cache.initialize_settings()
    shutil.copytree(master_folder, target_folder)


_copy_cache_folder.master = dict()  # temp_folder(create_dir=False)


@contextmanager
def redirect_output(target):
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    # TODO: change in 2.0
    # redirecting both of them to the same target for the moment
    # to assign to Testclient out
    sys.stdout = target
    sys.stderr = target
    try:
        yield
    finally:
        sys.stdout = original_stdout
        sys.stderr = original_stderr


class TestClient(object):
    """ Test wrap of the conans application to launch tests in the same way as
    in command line
    """

    def __init__(self, cache_folder=None, current_folder=None, servers=None, users=None,
                 requester_class=None, runner=None, path_with_spaces=True,
                 revisions_enabled=None, cpu_count=1, default_server_user=None,
                 cache_autopopulate=True):
        """
        current_folder: Current execution folder
        servers: dict of {remote_name: TestServer}
        logins is a list of (user, password) for auto input in order
        if required==> [("lasote", "mypass"), ("other", "otherpass")]
        """
        if default_server_user is not None:
            if servers is not None:
                raise Exception("Cannot define both 'servers' and 'default_server_user'")
            if users is not None:
                raise Exception("Cannot define both 'users' and 'default_server_user'")
            if default_server_user is True:
                server_users = {"user": "password"}
                users = {"default": [("user", "password")]}
            else:
                server_users = default_server_user
                users = {"default": list(default_server_user.items())}
            # Allow write permissions to users
            server = TestServer(users=server_users, write_permissions=[("*/*@*/*", "*")])
            servers = {"default": server}

        self.users = users
        if self.users is None:
            self.users = {"default": [(TESTING_REMOTE_PRIVATE_USER, TESTING_REMOTE_PRIVATE_PASS)]}

        if cache_autopopulate and (not cache_folder or not os.path.exists(cache_folder)):
            # Copy a cache folder already populated
            self.cache_folder = cache_folder or temp_folder(path_with_spaces, create_dir=False)
            _copy_cache_folder(self.cache_folder)
        else:
            self.cache_folder = cache_folder or temp_folder(path_with_spaces)

        self.requester_class = requester_class
        self.runner = runner

        if servers and len(servers) > 1 and not isinstance(servers, OrderedDict):
            raise Exception(textwrap.dedent("""
                Testing framework error: Servers should be an OrderedDict. e.g:
                    servers = OrderedDict()
                    servers["r1"] = server
                    servers["r2"] = TestServer()
            """))

        self.servers = servers or {}
        if servers is not False:  # Do not mess with registry remotes
            self.update_servers()
        self.current_folder = current_folder or temp_folder(path_with_spaces)

        # Once the client is ready, modify the configuration
        mkdir(self.current_folder)
        self.tune_conan_conf(cache_folder, cpu_count, revisions_enabled)

        self.out = RedirectedTestOutput()

    def load(self, filename):
        return load(os.path.join(self.current_folder, filename))

    @property
    def cache(self):
        # Returns a temporary cache object intended for inspecting it
        return ClientCache(self.cache_folder, TestBufferConanOutput())

    @property
    def base_folder(self):
        # Temporary hack to refactor ConanApp with less changes
        return self.cache_folder

    @property
    def storage_folder(self):
        return self.cache.store

    @property
    def requester(self):
        api = self.get_conan_api()
        api.create_app()
        return api.app.requester

    @property
    def proxy(self):
        api = self.get_conan_api()
        api.create_app()
        return api.app.proxy

    @property
    def _http_requester(self):
        # Check if servers are real
        real_servers = any(isinstance(s, (str, ArtifactoryServer))
                           for s in self.servers.values())
        if not real_servers:
            if self.requester_class:
                return self.requester_class(self.servers)
            else:
                return TestRequester(self.servers)

    def _set_revisions(self, value):
        value = "1" if value else "0"
        self.run("config set general.revisions_enabled={}".format(value))

    def enable_revisions(self):
        self._set_revisions(True)
        assert self.cache.config.revisions_enabled

    def disable_revisions(self):
        self._set_revisions(False)
        assert not self.cache.config.revisions_enabled

    def tune_conan_conf(self, cache_folder, cpu_count, revisions_enabled):
        # Create the default
        cache = self.cache
        _ = cache.config

        if cpu_count:
            replace_in_file(cache.conan_conf_path,
                            "# cpu_count = 1", "cpu_count = %s" % cpu_count,
                            output=Mock(), strict=not bool(cache_folder))

        if revisions_enabled is not None:
            self._set_revisions(revisions_enabled)
        elif "TESTING_REVISIONS_ENABLED" in os.environ:
            value = get_env("TESTING_REVISIONS_ENABLED", True)
            self._set_revisions(value)

    def update_servers(self):
        cache = self.cache
        Remotes().save(cache.remotes_path)
        registry = cache.registry

        for name, server in self.servers.items():
            if isinstance(server, ArtifactoryServer):
                registry.add(name, server.repo_api_url)
                self.users.update({name: [(ARTIFACTORY_DEFAULT_USER,
                                           ARTIFACTORY_DEFAULT_PASSWORD)]})
            elif isinstance(server, TestServer):
                registry.add(name, server.fake_url)
            else:
                registry.add(name, server)

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

    def get_conan_api_v2(self):
        user_io = MockedUserIO(self.users, out=sys.stderr)
        conan = ConanAPIV2(cache_folder=self.cache_folder, quiet=False, user_io=user_io,
                           http_requester=self._http_requester, runner=self.runner)
        return conan

    def get_conan_api_v1(self):
        user_io = MockedUserIO(self.users)
        conan = Conan(cache_folder=self.cache_folder, user_io=user_io,
                      http_requester=self._http_requester, runner=self.runner)
        return conan

    def get_conan_api(self):
        if os.getenv("CONAN_V2_CLI"):
            return self.get_conan_api_v2()
        else:
            return self.get_conan_api_v1()

    def get_default_host_profile(self):
        return self.cache.default_profile

    def get_default_build_profile(self):
        return self.cache.default_profile

    def run_cli(self, command_line, assert_error=False):
        conan = self.get_conan_api()
        self.api = conan
        if os.getenv("CONAN_V2_CLI"):
            command = Cli(conan)
        else:
            command = Command(conan)
        args = shlex.split(command_line)
        current_dir = os.getcwd()
        os.chdir(self.current_folder)
        old_path = sys.path[:]
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
        self._handle_cli_result(command_line, assert_error=assert_error, error=error)
        return error

    def run(self, command_line, assert_error=False):
        """ run a single command as in the command line.
            If user or password is filled, user_io will be mocked to return this
            tuple if required
        """
        from conans.test.utils.mocks import RedirectedTestOutput
        self.out = RedirectedTestOutput()  # Initialize each command
        with redirect_output(self.out):
            error = self.run_cli(command_line, assert_error=assert_error)
        return error

    def run_command(self, command, cwd=None, assert_error=False):
        output = TestBufferConanOutput()
        self.out = output
        runner = ConanRunner(output=output)
        ret = runner(command, cwd=cwd or self.current_folder)
        self._handle_cli_result(command, assert_error=assert_error, error=ret)
        return ret

    def _handle_cli_result(self, command, assert_error, error):
        if (assert_error and not error) or (not assert_error and error):
            if assert_error:
                msg = " Command succeeded (failure expected): "
            else:
                msg = " Command failed (unexpectedly): "
            exc_message = "\n{header}\n{cmd}\n{output_header}\n{output}\n{output_footer}\n".format(
                header='{:-^80}'.format(msg),
                output_header='{:-^80}'.format(" Output: "),
                output_footer='-' * 80,
                cmd=command,
                output=self.out
            )
            raise Exception(exc_message)

    def save(self, files, path=None, clean_first=False):
        """ helper metod, will store files in the current folder
        param files: dict{filename: filecontents}
        """
        path = path or self.current_folder
        if clean_first:
            shutil.rmtree(self.current_folder, ignore_errors=True)
        files = {f: str(content) for f, content in files.items()}
        save_files(path, files)
        if not files:
            mkdir(self.current_folder)

    def copy_assets(self, origin_folder, assets=None):
        copy_assets(origin_folder, self.current_folder, assets)

    # Higher level operations
    def remove_all(self):
        self.run("remove '*' -f")

    def export(self, ref, conanfile=GenConanfile(), args=None):
        """ export a ConanFile with as "ref" and return the reference with recipe revision
        """
        if conanfile:
            self.save({"conanfile.py": conanfile})
        self.run("export . {} {}".format(ref.full_str(), args or ""))
        rrev = self.cache.package_layout(ref).recipe_revision()
        return ref.copy_with_rev(rrev)

    def init_git_repo(self, files=None, branch=None, submodules=None, folder=None, origin_url=None,
                      main_branch="master"):
        if folder is not None:
            folder = os.path.join(self.current_folder, folder)
        else:
            folder = self.current_folder
        _, commit = create_local_git_repo(files, branch, submodules, folder=folder,
                                          origin_url=origin_url, main_branch=main_branch)
        return commit


class TurboTestClient(TestClient):
    tmp_json_name = ".tmp_json"

    def __init__(self, *args, **kwargs):
        if "users" not in kwargs and "default_server_user" not in kwargs:
            from collections import defaultdict
            kwargs["users"] = defaultdict(lambda: [("conan", "password")])

        super(TurboTestClient, self).__init__(*args, **kwargs)

    def create(self, ref, conanfile=GenConanfile(), args=None, assert_error=False):
        if conanfile:
            self.save({"conanfile.py": conanfile})
        full_str = "{}@".format(ref.full_str()) if not ref.user else ref.full_str()
        self.run("create . {} {} --json {}".format(full_str,
                                                   args or "", self.tmp_json_name),
                 assert_error=assert_error)
        rrev = self.cache.package_layout(ref).recipe_revision()
        data = json.loads(self.load(self.tmp_json_name))
        if assert_error:
            return None
        package_id = data["installed"][0]["packages"][0]["id"]
        package_ref = PackageReference(ref, package_id)
        prev = self.cache.package_layout(ref.copy_clear_rev()).package_revision(package_ref)
        return package_ref.copy_with_revs(rrev, prev)

    def upload_all(self, ref, remote=None, args=None, assert_error=False):
        remote = remote or list(self.servers.keys())[0]
        self.run("upload {} -c --all -r {} {}".format(ref.full_str(), remote, args or ""),
                 assert_error=assert_error)
        if not assert_error:
            remote_rrev, _ = self.servers[remote].server_store.get_last_revision(ref)
            return ref.copy_with_rev(remote_rrev)
        return

    def export_pkg(self, ref, conanfile=GenConanfile(), args=None, assert_error=False):
        if conanfile:
            self.save({"conanfile.py": conanfile})
        self.run("export-pkg . {} {} --json {}".format(ref.full_str(),
                                                       args or "", self.tmp_json_name),
                 assert_error=assert_error)
        rrev = self.cache.package_layout(ref).recipe_revision()
        data = json.loads(self.load(self.tmp_json_name))
        if assert_error:
            return None
        package_id = data["installed"][0]["packages"][0]["id"]
        package_ref = PackageReference(ref, package_id)
        prev = self.cache.package_layout(ref.copy_clear_rev()).package_revision(package_ref)
        return package_ref.copy_with_revs(rrev, prev)

    def recipe_exists(self, ref):
        return self.cache.package_layout(ref).recipe_exists()

    def package_exists(self, pref):
        return self.cache.package_layout(pref.ref).package_exists(pref)

    def recipe_revision(self, ref):
        return self.cache.package_layout(ref).recipe_revision()

    def package_revision(self, pref):
        return self.cache.package_layout(pref.ref).package_revision(pref)

    def search(self, pattern, remote=None, assert_error=False, args=None):
        remote = " -r={}".format(remote) if remote else ""
        self.run("search {} --json {} {} {}".format(pattern, self.tmp_json_name, remote,
                                                    args or ""),
                 assert_error=assert_error)
        data = json.loads(self.load(self.tmp_json_name))
        return data

    def massive_uploader(self, ref, revisions, num_prev, remote=None):
        """Uploads N revisions with M package revisions. The revisions can be specified like:
            revisions = [{"os": "Windows"}, {"os": "Linux"}], \
                        [{"os": "Macos"}], \
                        [{"os": "Solaris"}, {"os": "FreeBSD"}]

            IMPORTANT: Different settings keys will cause different recipe revisions
        """
        remote = remote or "default"
        ret = []
        for i, settings_groups in enumerate(revisions):
            tmp = []
            for settings in settings_groups:
                conanfile_gen = GenConanfile(). \
                    with_build_msg("REV{}".format(i)). \
                    with_package_file("file", env_var="MY_VAR")
                for s in settings.keys():
                    conanfile_gen = conanfile_gen.with_setting(s)
                for k in range(num_prev):
                    args = " ".join(["-s {}={}".format(key, value)
                                     for key, value in settings.items()])
                    with environment_append({"MY_VAR": str(k)}):
                        pref = self.create(ref, conanfile=conanfile_gen, args=args)
                        self.upload_all(ref, remote=remote)
                        tmp.append(pref)
                ret.append(tmp)
        return ret

    def init_svn_repo(self, subpath, files=None, repo_url=None):
        if not repo_url:
            repo_url = create_remote_svn_repo(temp_folder())
        _, rev = create_local_svn_checkout(files, repo_url, folder=self.current_folder,
                                           rel_project_path=subpath, delete_checkout=False)
        return rev


def get_free_port():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('localhost', 0))
    ret = sock.getsockname()[1]
    sock.close()
    return ret


class StoppableThreadBottle(threading.Thread):
    """
    Real server to test download endpoints
    """

    def __init__(self, host=None, port=None):
        self.host = host or "127.0.0.1"
        self.server = bottle.Bottle()
        self.port = port or get_free_port()
        super(StoppableThreadBottle, self).__init__(target=self.server.run,
                                                    kwargs={"host": self.host, "port": self.port})
        self.daemon = True
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def run_server(self):
        self.start()
        time.sleep(1)


def zipdir(path, zipfilename):
    with zipfile.ZipFile(zipfilename, 'w', zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(path):
            for f in files:
                file_path = os.path.join(root, f)
                if file_path == zipfilename:
                    continue
                relpath = os.path.relpath(file_path, path)
                z.write(file_path, relpath)
