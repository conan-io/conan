import copy
import json
import os
import platform
import re
import shlex
import shutil
import socket
import sys
import textwrap
import threading
import time
import traceback
import uuid
import zipfile
from collections import OrderedDict
from contextlib import contextmanager
from urllib.parse import urlsplit, urlunsplit

import bottle
import mock
import requests
from mock import Mock
from requests.exceptions import HTTPError
from webtest.app import TestApp

from conan.cli.exit_codes import SUCCESS, ERROR_GENERAL
from conan.internal.cache.cache import PackageLayout, RecipeLayout
from conan.internal.cache.home_paths import HomePaths
from conans import REVISIONS
from conan.api.conan_api import ConanAPI
from conan.api.model import Remote
from conan.cli.cli import Cli, _CONAN_INTERNAL_CUSTOM_COMMANDS_PATH
from conans.client.cache.cache import ClientCache
from conans.util.env import environment_update
from conans.errors import NotFoundException, ConanException
from conans.model.manifest import FileTreeManifest
from conans.model.package_ref import PkgReference
from conans.model.profile import Profile
from conans.model.recipe_ref import RecipeReference
from conans.model.settings import Settings
from conans.test.assets import copy_assets
from conans.test.assets.genconanfile import GenConanfile
from conans.test.conftest import default_profiles
from conans.test.utils.artifactory import ArtifactoryServer
from conans.test.utils.mocks import RedirectedInputStream
from conans.test.utils.mocks import RedirectedTestOutput
from conans.test.utils.scm import create_local_git_repo
from conans.test.utils.server_launcher import (TestServerLauncher)
from conans.test.utils.test_files import temp_folder
from conans.util.env import get_env
from conans.util.files import mkdir, save_files, save, load

NO_SETTINGS_PACKAGE_ID = "da39a3ee5e6b4b0d3255bfef95601890afd80709"


def inc_recipe_manifest_timestamp(cache, reference, inc_time):
    ref = RecipeReference.loads(reference)
    path = cache.get_latest_recipe_reference(ref).export()
    manifest = FileTreeManifest.load(path)
    manifest.time += inc_time
    manifest.save(path)


def inc_package_manifest_timestamp(cache, package_reference, inc_time):
    path = cache.get_latest_package_reference(package_reference).package()
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


class TestRequester:
    """Fake requests module calling server applications
    with TestApp"""

    def __init__(self, test_servers):
        self.test_servers = test_servers
        self.utils = Mock()
        self.utils.default_user_agent.return_value = "TestRequester Agent"

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

    def head(self, url, **kwargs):
        app, url = self._prepare_call(url, kwargs)
        if app:
            response = app.head(url, **kwargs)
            return TestingResponse(response)
        else:
            return requests.head(url, **kwargs)

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
            auth = kwargs.pop("auth", None)
            if auth and isinstance(auth, tuple):
                app.set_authorization(("Basic", auth))
            kwargs.pop("cert", None)
            kwargs.pop("timeout", None)
            if "data" in kwargs:
                total_data = kwargs["data"].read()
                kwargs["params"] = total_data
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
            if isinstance(kwargs.get("auth"), tuple):  # For download(..., auth=(user, paswd))
                return
            mock_request = Mock()
            mock_request.headers = {}
            kwargs["auth"](mock_request)
            if kwargs.get("headers") is None:
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
            write_permissions = [("*/*@*/*", "*")]
        if users is None:
            users = {"admin": "password"}

        if server_capabilities is None:
            server_capabilities = [REVISIONS]
        elif REVISIONS not in server_capabilities:
            server_capabilities.append(REVISIONS)

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
        ref = self.test_server.server_store.get_last_revision(ref)
        return ref

    def recipe_revision_time(self, ref):
        if not ref.revision:
            raise Exception("Pass a ref with revision (Testing framework)")
        return self.test_server.server_store.get_revision_time(ref)

    def latest_package(self, pref):
        if not pref.ref.revision:
            raise Exception("Pass a pref with .rev.revision (Testing framework)")
        prev = self.test_server.server_store.get_last_package_revision(pref)
        _tmp = copy.copy(prev)
        _tmp.revision = prev
        return _tmp

    def package_revision_time(self, pref):
        if not pref:
            raise Exception("Pass a pref with revision (Testing framework)")
        tmp = self.test_server.server_store.get_package_revision_time(pref)
        return tmp


if get_env("CONAN_TEST_WITH_ARTIFACTORY", False):
    TestServer = ArtifactoryServer


@contextmanager
def redirect_output(stderr, stdout=None):
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    # TODO: change in 2.0
    # redirecting both of them to the same target for the moment
    # to assign to Testclient out
    sys.stdout = stdout or stderr
    sys.stderr = stderr
    try:
        yield
    finally:
        sys.stdout = original_stdout
        sys.stderr = original_stderr


@contextmanager
def redirect_input(target):
    original_stdin = sys.stdin
    sys.stdin = target
    try:
        yield
    finally:
        sys.stdin = original_stdin


class TestClient:
    """ Test wrap of the conans application to launch tests in the same way as
    in command line
    """
    # Preventing Pytest collects any tests from here
    __test__ = False

    def __init__(self, cache_folder=None, current_folder=None, servers=None, inputs=None,
                 requester_class=None, path_with_spaces=True,
                 default_server_user=None, light=False, custom_commands_folder=None):
        """
        current_folder: Current execution folder
        servers: dict of {remote_name: TestServer}
        logins is a list of (user, password) for auto input in order
        if required==> [("lasote", "mypass"), ("other", "otherpass")]
        """
        if default_server_user is not None:
            assert isinstance(default_server_user, bool), \
                "default_server_user has to be True or False"
            if servers is not None:
                raise Exception("Cannot define both 'servers' and 'default_server_user'")
            if inputs is not None:
                raise Exception("Cannot define both 'inputs' and 'default_server_user'")

            server_users = {"admin": "password"}
            inputs = ["admin", "password"]

            # Allow writing permissions to users
            server = TestServer(users=server_users, write_permissions=[("*/*@*/*", "*")])
            servers = {"default": server}

        # Adding the .conan2, so we know clearly while debugging this is a cache folder
        self.cache_folder = cache_folder or os.path.join(temp_folder(path_with_spaces), ".conan2")

        self.requester_class = requester_class

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

        self.out = ""
        self.stdout = RedirectedTestOutput()
        self.stderr = RedirectedTestOutput()
        self.user_inputs = RedirectedInputStream([])
        self.inputs = inputs or []

        # create default profile
        if light:
            text = "[settings]\nos=Linux"  # Needed at least build-os
            save(self.cache.settings_path, "os: [Linux]")
        else:
            text = default_profiles[platform.system()]
        save(self.cache.default_profile_path, text)
        # Using internal env variable to add another custom commands folder
        self._custom_commands_folder = custom_commands_folder

    def load(self, filename):
        return load(os.path.join(self.current_folder, filename))

    @property
    def cache(self):
        # Returns a temporary cache object intended for inspecting it
        api = ConanAPI(cache_folder=self.cache_folder)
        global_conf = api.config.global_conf

        class MyCache(ClientCache, HomePaths):  # Temporary class to avoid breaking all tests
            def __init__(self, cache_folder):
                ClientCache.__init__(self, cache_folder, global_conf)
                HomePaths.__init__(self, cache_folder)

            @property
            def plugins_path(self):  # Temporary to not break tests
                return os.path.join(self.cache_folder, "extensions", "plugins")

            @property
            def default_profile_path(self):
                return os.path.join(self.cache_folder, "profiles", "default")

        return MyCache(self.cache_folder)

    @property
    def base_folder(self):
        # Temporary hack to refactor ConanApp with less changes
        return self.cache_folder

    @property
    def storage_folder(self):
        return self.cache.store

    def update_servers(self):
        api = ConanAPI(cache_folder=self.cache_folder)
        for r in api.remotes.list():
            api.remotes.remove(r.name)

        for name, server in self.servers.items():
            if isinstance(server, ArtifactoryServer):
                api.remotes.add(Remote(name, server.repo_api_url))
            elif isinstance(server, TestServer):
                api.remotes.add(Remote(name, server.fake_url))
            else:
                api.remotes.add(Remote(name, server))

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

    @contextmanager
    def mocked_servers(self, requester=None):
        _req = requester or TestRequester(self.servers)
        with mock.patch("conans.client.rest.conan_requester.requests", _req):
            yield

    @contextmanager
    def mocked_io(self):
        def mock_get_pass(*args, **kwargs):
            return self.user_inputs.readline()

        with redirect_output(self.stderr, self.stdout):
            with redirect_input(self.user_inputs):
                with mock.patch("getpass.getpass", mock_get_pass):
                    yield

    def _run_cli(self, command_line, assert_error=False):
        current_dir = os.getcwd()
        os.chdir(self.current_folder)
        old_path = sys.path[:]
        old_modules = list(sys.modules.keys())

        args = shlex.split(command_line)

        try:
            self.api = ConanAPI(cache_folder=self.cache_folder)
            command = Cli(self.api)
        except ConanException as e:
            sys.stderr.write("Error in Conan initialization: {}".format(e))
            return ERROR_GENERAL

        error = SUCCESS
        trace = None
        try:
            if self._custom_commands_folder:
                with environment_update({_CONAN_INTERNAL_CUSTOM_COMMANDS_PATH:
                                             self._custom_commands_folder}):
                    command.run(args)
            else:
                command.run(args)
        except BaseException as e:  # Capture all exceptions as argparse
            trace = traceback.format_exc()
            error = command.exception_exit_error(e)
        finally:
            sys.path = old_path
            os.chdir(current_dir)
            # Reset sys.modules to its prev state. A .copy() DOES NOT WORK
            added_modules = set(sys.modules).difference(old_modules)
            for added in added_modules:
                sys.modules.pop(added, None)
        self._handle_cli_result(command_line, assert_error=assert_error, error=error, trace=trace)
        return error

    def run(self, command_line, assert_error=False, redirect_stdout=None, redirect_stderr=None, inputs=None):
        """ run a single command as in the command line.
            If user or password is filled, user_io will be mocked to return this
            tuple if required
        """
        from conans.test.utils.mocks import RedirectedTestOutput
        with environment_update({"NO_COLOR": "1"}):  # Not initialize colorama in testing
            self.user_inputs = RedirectedInputStream(inputs or self.inputs)
            self.stdout = RedirectedTestOutput()  # Initialize each command
            self.stderr = RedirectedTestOutput()
            self.out = ""
            with self.mocked_io():
                real_servers = any(isinstance(s, (str, ArtifactoryServer))
                                   for s in self.servers.values())
                http_requester = None
                if not real_servers:
                    if self.requester_class:
                        http_requester = self.requester_class(self.servers)
                    else:
                        http_requester = TestRequester(self.servers)
                try:
                    if http_requester:
                        with self.mocked_servers(http_requester):
                            return self._run_cli(command_line, assert_error=assert_error)
                    else:
                        return self._run_cli(command_line, assert_error=assert_error)
                finally:
                    self.stdout = str(self.stdout)
                    self.stderr = str(self.stderr)
                    self.out = self.stderr + self.stdout
                    if redirect_stdout:
                        save(os.path.join(self.current_folder, redirect_stdout), self.stdout)
                    if redirect_stderr:
                        save(os.path.join(self.current_folder, redirect_stderr), self.stderr)

    def run_command(self, command, cwd=None, assert_error=False):
        from conans.test.utils.mocks import RedirectedTestOutput
        self.stdout = RedirectedTestOutput()  # Initialize each command
        self.stderr = RedirectedTestOutput()
        try:
            with redirect_output(self.stderr, self.stdout):
                from conans.util.runners import conan_run
                ret = conan_run(command, cwd=cwd or self.current_folder)
        finally:
            self.stdout = str(self.stdout)
            self.stderr = str(self.stderr)
            self.out = self.stderr + self.stdout
        self._handle_cli_result(command, assert_error=assert_error, error=ret)
        return ret

    def _handle_cli_result(self, command, assert_error, error, trace=None):
        if (assert_error and not error) or (not assert_error and error):
            if assert_error:
                msg = " Command succeeded (failure expected): "
            else:
                msg = " Command failed (unexpectedly): "
            exc_message = "\n{header}\n{cmd}\n{output_header}\n{output}\n".format(
                header='{:=^80}'.format(msg),
                output_header='{:=^80}'.format(" Output: "),
                cmd=command,
                output=str(self.stderr) + str(self.stdout) + "\n" + str(self.out)
            )
            if trace:
                exc_message += '{:=^80}'.format(" Traceback: ") + f"\n{trace}"
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

    def save_home(self, files):
        self.save(files, path=self.cache_folder)

    def copy_assets(self, origin_folder, assets=None):
        copy_assets(origin_folder, self.current_folder, assets)

    # Higher level operations
    def remove_all(self):
        self.run("remove '*' -c")

    def export(self, ref, conanfile=GenConanfile(), args=None):
        """ export a ConanFile with as "ref" and return the reference with recipe revision
        """
        if conanfile:
            self.save({"conanfile.py": conanfile})
        if ref:
            self.run(f"export . --name={ref.name} --version={ref.version} --user={ref.user} --channel={ref.channel}")
        else:
            self.run("export .")
        tmp = copy.copy(ref)
        tmp.revision = None
        rrev = self.cache.get_latest_recipe_reference(tmp).revision
        tmp = copy.copy(ref)
        tmp.revision = rrev
        return tmp

    def alias(self, source, target):
        """
        creates a new recipe with "conan new alias" template, "conan export" it, and remove it
        @param source: the reference of the current recipe
        @param target: the target reference that this recipe is pointing (aliasing to)
        """
        source = RecipeReference.loads(source)
        target = target.split("/", 1)[1]
        self.run(f"new alias -d name={source.name} -d version={source.version} "
                 f"-d target={target} -f")
        user = f"--user={source.user}" if source.user else ""
        channel = f"--channel={source.channel}" if source.channel else ""
        self.run(f"export . {user} {channel}")
        os.remove(os.path.join(self.current_folder, "conanfile.py"))

    def init_git_repo(self, files=None, branch=None, submodules=None, folder=None, origin_url=None,
                      main_branch="master"):
        if folder is not None:
            folder = os.path.join(self.current_folder, folder)
        else:
            folder = self.current_folder
        _, commit = create_local_git_repo(files, branch, submodules, folder=folder,
                                          origin_url=origin_url, main_branch=main_branch)
        return commit

    def get_latest_package_reference(self, ref, package_id=None) -> PkgReference:
        """Get the latest PkgReference given a ConanReference"""
        ref_ = RecipeReference.loads(ref) if isinstance(ref, str) else ref
        latest_rrev = self.cache.get_latest_recipe_reference(ref_)
        if package_id:
            pref = PkgReference(latest_rrev, package_id)
        else:
            package_ids = self.cache.get_package_references(latest_rrev)
            # Let's check if there are several packages because we don't want random behaviours
            assert len(package_ids) == 1, f"There are several packages for {latest_rrev}, please, " \
                                          f"provide a single package_id instead" \
                                          if len(package_ids) > 0 else "No binary packages found"
            pref = package_ids[0]
        return self.cache.get_latest_package_reference(pref)

    def get_latest_pkg_layout(self, pref: PkgReference) -> PackageLayout:
        """Get the latest PackageLayout given a file reference"""
        # Let's make it easier for all the test clients
        latest_prev = self.cache.get_latest_package_reference(pref)
        pkg_layout = self.cache.pkg_layout(latest_prev)
        return pkg_layout

    def get_latest_ref_layout(self, ref) -> RecipeLayout:
        """Get the latest RecipeLayout given a file reference"""
        ref_layout = self.cache.recipe_layout(ref)
        return ref_layout

    def get_default_host_profile(self):
        api = ConanAPI(cache_folder=self.cache_folder)
        return api.profiles.get_profile([api.profiles.get_default_host()])

    def get_default_build_profile(self):
        api = ConanAPI(cache_folder=self.cache_folder)
        return api.profiles.get_profile([api.profiles.get_default_build()])

    def recipe_exists(self, ref):
        rrev = self.cache.get_recipe_revisions_references(ref)
        return True if rrev else False

    def package_exists(self, pref):
        prev = self.cache.get_package_revisions_references(pref)
        return True if prev else False

    def assert_listed_require(self, requires, build=False, python=False, test=False,
                              test_package=False):
        """ parses the current command output, and extract the first "Requirements" section
        """
        lines = self.out.splitlines()
        if test_package:
            line_req = lines.index("======== Launching test_package ========")
            lines = lines[line_req:]
        header = "Requirements" if not build else "Build requirements"
        if python:
            header = "Python requires"
        if test:
            header = "Test requirements"
        line_req = lines.index(header)
        reqs = []
        for line in lines[line_req+1:]:
            if not line.startswith("    "):
                break
            reqs.append(line.strip())
        for r, kind in requires.items():
            for req in reqs:
                if req.startswith(r) and req.endswith(kind):
                    break
            else:
                raise AssertionError(f"Cant find {r}-{kind} in {reqs}")

    def assert_overrides(self, overrides):
        """ parses the current command output, and extract the first "Requirements" section
        """
        lines = self.out.splitlines()
        header = "Overrides"
        line_req = lines.index(header)
        reqs = []
        for line in lines[line_req+1:]:
            if not line.startswith("    "):
                break
            reqs.append(line.strip())
        for r, o in overrides.items():
            msg = f"{r}: {o}"
            if msg not in reqs:
                raise AssertionError(f"Cant find {msg} in {reqs}")

    def assert_listed_binary(self, requires, build=False, test=False, test_package=False):
        """ parses the current command output, and extract the second "Requirements" section
        belonging to the computed package binaries
        """
        lines = self.out.splitlines()
        if test_package:
            line_req = lines.index("======== Launching test_package ========")
            lines = lines[line_req:]
        line_req = lines.index("======== Computing necessary packages ========")
        header = "Requirements" if not build else "Build requirements"
        if test:
            header = "Test requirements"
        line_req = lines.index(header, line_req)

        reqs = []
        for line in lines[line_req+1:]:
            if not line.startswith("    "):
                break
            reqs.append(line.strip())
        for r, kind in requires.items():
            package_id, binary = kind
            for req in reqs:
                if req.startswith(r) and package_id in req and req.endswith(binary):
                    break
            else:
                raise AssertionError(f"Cant find {r}-{kind} in {reqs}")

    def created_test_build_folder(self, ref):
        build_folder = re.search(r"{} \(test package\): Test package build: (.*)".format(str(ref)),
                                 str(self.out)).group(1)
        return build_folder.replace("\\", "/")

    def created_package_id(self, ref):
        package_id = re.search(r"{}: Package '(\S+)' created".format(str(ref)),
                               str(self.out)).group(1)
        return package_id

    def created_package_revision(self, ref):
        package_id = re.search(r"{}: Created package revision (\S+)".format(str(ref)),
                               str(self.out)).group(1)
        return package_id

    def created_package_reference(self, ref):
        pref = re.search(r"{}: Full package reference: (\S+)".format(str(ref)),
                               str(self.out)).group(1)
        return PkgReference.loads(pref)

    def exported_recipe_revision(self):
        return re.search(r": Exported: .*#(\S+)", str(self.out)).group(1)

    def exported_layout(self):
        m = re.search(r": Exported: (\S+)", str(self.out)).group(1)
        ref = RecipeReference.loads(m)
        return self.cache.recipe_layout(ref)

    def created_layout(self):
        pref = re.search(r"(?s:.*)Full package reference: (\S+)", str(self.out)).group(1)
        pref = PkgReference.loads(pref)
        return self.cache.pkg_layout(pref)


class TurboTestClient(TestClient):

    def __init__(self, *args, **kwargs):
        super(TurboTestClient, self).__init__(*args, **kwargs)

    def create(self, ref, conanfile=GenConanfile(), args=None, assert_error=False):
        if conanfile:
            self.save({"conanfile.py": conanfile})
        full_str = f"--name={ref.name} --version={ref.version}"
        if ref.user:
            full_str += f" --user={ref.user}"
        if ref.channel:
            full_str += f" --channel={ref.channel}"
        self.run("create . {} {}".format(full_str, args or ""),
                 assert_error=assert_error)

        tmp = copy.copy(ref)
        tmp.revision = None
        ref = self.cache.get_latest_recipe_reference(tmp)

        if assert_error:
            return None

        package_id = self.created_package_id(ref)
        package_ref = PkgReference(ref, package_id)
        tmp = copy.copy(package_ref)
        tmp.revision = None
        prevs = self.cache.get_package_revisions_references(tmp, only_latest_prev=True)
        prev = prevs[0]

        return prev

    def upload_all(self, ref, remote=None, args=None, assert_error=False):
        remote = remote or list(self.servers.keys())[0]
        self.run("upload {} -c -r {} {}".format(ref.repr_notime(), remote, args or ""),
                 assert_error=assert_error)
        if not assert_error:
            remote_rrev, _ = self.servers[remote].server_store.get_last_revision(ref)
            _tmp = copy.copy(ref)
            _tmp.revision = remote_rrev
            return _tmp

    def export_pkg(self, ref, conanfile=GenConanfile(), args=None, assert_error=False):
        if conanfile:
            self.save({"conanfile.py": conanfile})
        self.run("export-pkg . {} {}".format(repr(ref),  args or ""),
                 assert_error=assert_error)
        # FIXME: What is this line? rrev is not used, is it checking existance or something?
        rrev = self.cache.get_latest_recipe_reference(ref)

        if assert_error:
            return None
        package_id = re.search(r"{}:(\S+)".format(str(ref)), str(self.out)).group(1)
        package_ref = PkgReference(ref, package_id)
        prev = self.cache.get_latest_package_reference(package_ref)
        _tmp = copy.copy(package_ref)
        _tmp.revision = prev
        return _tmp

    def recipe_revision(self, ref):
        tmp = copy.copy(ref)
        tmp.revision = None
        latest_rrev = self.cache.get_latest_recipe_reference(tmp)
        return latest_rrev.revision

    def package_revision(self, pref):
        tmp = copy.copy(pref)
        tmp.revision = None
        latest_prev = self.cache.get_latest_package_reference(tmp)
        return latest_prev.revision

    # FIXME: 2.0: adapt this function to using the new "conan list xxxx" and recover the xfail tests
    def search(self, pattern, remote=None, assert_error=False, args=None):
        remote = " -r={}".format(remote) if remote else ""
        self.run("search {} --json {} {} {}".format(pattern, ".tmp.json", remote,
                                                    args or ""),
                 assert_error=assert_error)
        data = json.loads(self.load(".tmp.json"))
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
                    with environment_update({"MY_VAR": str(k)}):
                        pref = self.create(ref, conanfile=conanfile_gen, args=args)
                        self.upload_all(ref, remote=remote)
                        tmp.append(pref)
                ret.append(tmp)
        return ret


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
