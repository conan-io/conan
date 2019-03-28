import errno
import json
import os
import random
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import uuid
from collections import Counter, OrderedDict
from contextlib import contextmanager

import bottle
import nose
import requests
import six
from mock import Mock
from six import StringIO
from six.moves.urllib.parse import quote, urlsplit, urlunsplit
from webtest.app import TestApp

from conans import tools, load
from conans.client.cache.cache import ClientCache
from conans.client.cache.remote_registry import dump_registry
from conans.client.command import Command
from conans.client.conan_api import Conan, get_request_timeout, migrate_and_get_cache
from conans.client.conan_command_output import CommandOutputer
from conans.client.hook_manager import HookManager
from conans.client.loader import ProcessedProfile
from conans.client.output import ConanOutput
from conans.client.rest.conan_requester import ConanRequester
from conans.client.rest.uploader_downloader import IterableToFileAdapter
from conans.client.tools import environment_append
from conans.client.tools.files import chdir
from conans.client.tools.files import replace_in_file
from conans.client.tools.scm import Git, SVN
from conans.client.tools.win import get_cased_path
from conans.client.userio import UserIO
from conans.errors import NotFoundException, RecipeNotFoundException, PackageNotFoundException
from conans.model.manifest import FileTreeManifest
from conans.model.profile import Profile
from conans.model.ref import ConanFileReference, PackageReference
from conans.model.settings import Settings
from conans.server.revision_list import _RevisionEntry
from conans.test.utils.runner import TestRunner
from conans.test.utils.server_launcher import (TESTING_REMOTE_PRIVATE_PASS,
                                               TESTING_REMOTE_PRIVATE_USER,
                                               TestServerLauncher)
from conans.test.utils.test_files import temp_folder
from conans.tools import set_global_instances
from conans.util.env_reader import get_env
from conans.util.files import mkdir, save, save_files
from conans.util.log import logger

NO_SETTINGS_PACKAGE_ID = "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9"
ARTIFACTORY_DEFAULT_USER = "admin"
ARTIFACTORY_DEFAULT_PASSWORD = "password"
ARTIFACTORY_DEFAULT_URL = "http://localhost:8090/artifactory"


def inc_recipe_manifest_timestamp(cache, reference, inc_time):
    ref = ConanFileReference.loads(reference)
    path = cache.export(ref)
    manifest = FileTreeManifest.load(path)
    manifest.time += inc_time
    manifest.save(path)


def inc_package_manifest_timestamp(cache, package_reference, inc_time):
    pref = PackageReference.loads(package_reference)
    path = cache.package(pref)
    manifest = FileTreeManifest.load(path)
    manifest.time += inc_time
    manifest.save(path)


def test_processed_profile(profile=None, settings=None):
    if profile is None:
        profile = Profile()
    if profile.processed_settings is None:
        profile.processed_settings = settings or Settings()
    return ProcessedProfile(profile=profile)


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


class ArtifactoryServerStore(object):

    def __init__(self, repo_url, user, password):
        self._user = user or ARTIFACTORY_DEFAULT_USER
        self._password = password or ARTIFACTORY_DEFAULT_PASSWORD
        self._repo_url = repo_url

    @property
    def _auth(self):
        return self._user, self._password

    @staticmethod
    def _root_recipe(ref):
        return "{}/{}/{}/{}".format(ref.user, ref.name, ref.version, ref.channel)

    @staticmethod
    def _ref_index(ref):
        return "{}/index.json".format(ArtifactoryServerStore._root_recipe(ref))

    @staticmethod
    def _pref_index(pref):
        tmp = ArtifactoryServerStore._root_recipe(pref.ref)
        return "{}/{}/package/{}/index.json".format(tmp, pref.ref.revision, pref.id)

    def get_recipe_revisions(self, ref):
        time.sleep(0.1)  # Index appears to not being updated immediately after a remove
        url = "{}/{}".format(self._repo_url, self._ref_index(ref))
        response = requests.get(url, auth=self._auth)
        response.raise_for_status()
        the_json = response.json()
        if not the_json["revisions"]:
            raise RecipeNotFoundException(ref)
        tmp = [_RevisionEntry(i["revision"], i["time"]) for i in the_json["revisions"]]
        return tmp

    def get_package_revisions(self, pref):
        time.sleep(0.1)  # Index appears to not being updated immediately
        url = "{}/{}".format(self._repo_url, self._pref_index(pref))
        response = requests.get(url, auth=self._auth)
        response.raise_for_status()
        the_json = response.json()
        if not the_json["revisions"]:
            raise PackageNotFoundException(pref)
        tmp = [_RevisionEntry(i["revision"], i["time"]) for i in the_json["revisions"]]
        return tmp

    def get_last_revision(self, ref):
        revisions = self.get_recipe_revisions(ref)
        return revisions[0]

    def get_last_package_revision(self, ref):
        revisions = self.get_package_revisions(ref)
        return revisions[0]

    def package_exists(self, pref):
        try:
            if pref.revision:
                path = self.server_store.package(pref)
            else:
                path = self.test_server.server_store.package_revisions_root(pref)
            return self.test_server.server_store.path_exists(path)
        except NotFoundException:  # When resolves the latest and there is no package
            return False


class ArtifactoryServer(object):

    def __init__(self, url=None, user=None, password=None, server_capabilities=None):
        self._user = user or ARTIFACTORY_DEFAULT_USER
        self._password = password or ARTIFACTORY_DEFAULT_PASSWORD
        self._url = url or ARTIFACTORY_DEFAULT_URL
        self._repo_name = "conan_{}".format(str(uuid.uuid4()).replace("-", ""))
        self.create_repository()
        self.server_store = ArtifactoryServerStore(self.repo_url, self._user, self._password)
        if server_capabilities is not None:
            raise nose.SkipTest("The Artifactory Server can't adjust capabilities")

    @property
    def _auth(self):
        return self._user, self._password

    @property
    def repo_url(self):
        return "{}/{}".format(self._url, self._repo_name)

    @property
    def repo_api_url(self):
        return "{}/api/conan/{}".format(self._url, self._repo_name)

    def recipe_revision_time(self, ref):
        revs = self.server_store.get_recipe_revisions(ref)
        for r in revs:
            if r.revision == ref.revision:
                return r.time
        return None

    def package_revision_time(self, pref):
        revs = self.server_store.get_package_revisions(pref)
        for r in revs:
            if r.revision == pref.revision:
                return r.time
        return None

    def create_repository(self):
        url = "{}/api/repositories/{}".format(self._url, self._repo_name)
        config = {"key": self._repo_name, "rclass": "local", "packageType": "conan"}
        ret = requests.put(url, auth=self._auth, json=config)
        ret.raise_for_status()

    def package_exists(self, pref):
        try:
            revisions = self.server_store.get_package_revisions(pref)
            if pref.revision:
                for r in revisions:
                    if pref.revision == r.revision:
                        return True
                return False
            return True
        except Exception:  # When resolves the latest and there is no package
            return False

    def recipe_exists(self, ref):
        try:
            revisions = self.server_store.get_recipe_revisions(ref)
            if ref.revision:
                for r in revisions:
                    if ref.revision == r.revision:
                        return True
                return False
            return True
        except Exception:  # When resolves the latest and there is no package
            return False


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
                path = self.test_server.server_store.conan(ref)
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


def create_local_svn_checkout(files, repo_url, rel_project_path=None,
                              commit_msg='default commit message', delete_checkout=True,
                              folder=None):
    tmp_dir = folder or temp_folder()
    try:
        rel_project_path = rel_project_path or str(uuid.uuid4())
        # Do not use SVN class as it is what we will be testing
        subprocess.check_output('svn co "{url}" "{path}"'.format(url=repo_url,
                                                                 path=tmp_dir),
                                shell=True)
        tmp_project_dir = os.path.join(tmp_dir, rel_project_path)
        mkdir(tmp_project_dir)
        save_files(tmp_project_dir, files)
        with chdir(tmp_project_dir):
            subprocess.check_output("svn add .", shell=True)
            subprocess.check_output('svn commit -m "{}"'.format(commit_msg), shell=True)
            if SVN.get_version() >= SVN.API_CHANGE_VERSION:
                rev = subprocess.check_output("svn info --show-item revision",
                                              shell=True).decode().strip()
            else:
                import xml.etree.ElementTree as ET
                output = subprocess.check_output("svn info --xml", shell=True).decode().strip()
                root = ET.fromstring(output)
                rev = root.findall("./entry")[0].get("revision")
        project_url = repo_url + "/" + quote(rel_project_path.replace("\\", "/"))
        return project_url, rev
    finally:
        if delete_checkout:
            shutil.rmtree(tmp_dir, ignore_errors=False, onerror=try_remove_readonly)


def create_remote_svn_repo(folder=None):
    tmp_dir = folder or temp_folder()
    subprocess.check_output('svnadmin create "{}"'.format(tmp_dir), shell=True)
    return SVN.file_protocol + quote(tmp_dir.replace("\\", "/"), safe='/:')


def try_remove_readonly(func, path, exc):  # TODO: May promote to conan tools?
    # src: https://stackoverflow.com/questions/1213706/what-user-do-python-scripts-run-as-in-windows
    excvalue = exc[1]
    if func in (os.rmdir, os.remove, os.unlink) and excvalue.errno == errno.EACCES:
        os.chmod(path, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)  # 0777
        func(path)
    else:
        raise OSError("Cannot make read-only %s" % path)


class SVNLocalRepoTestCase(unittest.TestCase):
    path_with_spaces = True

    def _create_local_svn_repo(self):
        folder = os.path.join(self._tmp_folder, 'repo_server')
        return create_remote_svn_repo(folder)

    def gimme_tmp(self, create=True):
        tmp = os.path.join(self._tmp_folder, str(uuid.uuid4()))
        if create:
            os.makedirs(tmp)
        return tmp

    def create_project(self, files, rel_project_path=None, commit_msg='default commit message',
                       delete_checkout=True):
        tmp_dir = self.gimme_tmp()
        return create_local_svn_checkout(files, self.repo_url, rel_project_path=rel_project_path,
                                         commit_msg=commit_msg, delete_checkout=delete_checkout,
                                         folder=tmp_dir)

    def run(self, *args, **kwargs):
        tmp_folder = tempfile.mkdtemp(suffix='_conans')
        try:
            self._tmp_folder = os.path.join(tmp_folder, 'path with spaces'
                                            if self.path_with_spaces else 'pathwithoutspaces')
            os.makedirs(self._tmp_folder)
            self.repo_url = self._create_local_svn_repo()
            super(SVNLocalRepoTestCase, self).run(*args, **kwargs)
        finally:
            shutil.rmtree(tmp_folder, ignore_errors=False, onerror=try_remove_readonly)


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

    def __init__(self, base_folder=None, current_folder=None, servers=None, users=None,
                 requester_class=None, runner=None, path_with_spaces=True,
                 revisions_enabled=None, cpu_count=1):
        """
        storage_folder: Local storage path
        current_folder: Current execution folder
        servers: dict of {remote_name: TestServer}
        logins is a list of (user, password) for auto input in order
        if required==> [("lasote", "mypass"), ("other", "otherpass")]
        """

        self.all_output = ""  # For debugging purpose, append all the run outputs
        self.users = users
        if self.users is None:
            self.users = {"default": [(TESTING_REMOTE_PRIVATE_USER, TESTING_REMOTE_PRIVATE_PASS)]}

        self.base_folder = base_folder or temp_folder(path_with_spaces)

        # Define storage_folder, if not, it will be read from conf file & pointed to real user home
        self.storage_folder = os.path.join(self.base_folder, ".conan", "data")
        self.cache = ClientCache(self.base_folder, self.storage_folder,
                                 TestBufferConanOutput())

        self.requester_class = requester_class
        self.conan_runner = runner

        if revisions_enabled is None:
            revisions_enabled = get_env("TESTING_REVISIONS_ENABLED", False)

        self.tune_conan_conf(base_folder, cpu_count, revisions_enabled)

        if servers and len(servers) > 1 and not isinstance(servers, OrderedDict):
            raise Exception("""Testing framework error: Servers should be an OrderedDict. e.g:
servers = OrderedDict()
servers["r1"] = server
servers["r2"] = TestServer()
""")

        self.servers = servers or {}
        if servers is not False:  # Do not mess with registry remotes
            self.update_servers()

        self.init_dynamic_vars()

        logger.debug("Client storage = %s" % self.storage_folder)
        self.current_folder = current_folder or temp_folder(path_with_spaces)

    def _set_revisions(self, value):
        current_conf = load(self.cache.conan_conf_path)
        if "revisions_enabled" in current_conf:  # Invalidate any previous value to be sure
            replace_in_file(self.cache.conan_conf_path, "revisions_enabled", "#revisions_enabled",
                            output=TestBufferConanOutput())

        replace_in_file(self.cache.conan_conf_path,
                        "[general]", "[general]\nrevisions_enabled = %s" % value,
                        output=TestBufferConanOutput())
        # Invalidate the cached config
        self.cache.invalidate()

    def enable_revisions(self):
        self._set_revisions("1")
        assert self.cache.config.revisions_enabled

    def disable_revisions(self):
        self._set_revisions("0")
        assert not self.cache.config.revisions_enabled

    def tune_conan_conf(self, base_folder, cpu_count, revisions_enabled):
        # Create the default
        self.cache.config

        if cpu_count:
            replace_in_file(self.cache.conan_conf_path,
                            "# cpu_count = 1", "cpu_count = %s" % cpu_count,
                            output=TestBufferConanOutput(), strict=not bool(base_folder))

        current_conf = load(self.cache.conan_conf_path)
        if "revisions_enabled" in current_conf:  # Invalidate any previous value to be sure
            replace_in_file(self.cache.conan_conf_path, "revisions_enabled", "#revisions_enabled",
                            output=TestBufferConanOutput())
        if revisions_enabled:
            replace_in_file(self.cache.conan_conf_path,
                            "[general]", "[general]\nrevisions_enabled = 1",
                            output=TestBufferConanOutput())

        # Invalidate the cached config
        self.cache.invalidate()

    def update_servers(self):
        save(self.cache.registry_path, dump_registry({}, {}, {}))
        registry = self.cache.registry

        def add_server_to_registry(name, server):
            if isinstance(server, ArtifactoryServer):
                registry.remotes.add(name, server.repo_api_url)
                self.users.update({name: [(ARTIFACTORY_DEFAULT_USER,
                                           ARTIFACTORY_DEFAULT_PASSWORD)]})
            elif isinstance(server, TestServer):
                registry.remotes.add(name, server.fake_url)
            else:
                registry.remotes.add(name, server)

        for name, server in self.servers.items():
            if name == "default":
                add_server_to_registry(name, server)

        for name, server in self.servers.items():
            if name != "default":
                add_server_to_registry(name, server)

    @property
    def default_compiler_visual_studio(self):
        settings = self.cache.default_profile.settings
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
        self.cache = ClientCache(self.base_folder, self.storage_folder, output)
        self.runner = TestRunner(output, runner=self.conan_runner)

        # Check if servers are real
        real_servers = False
        for server in self.servers.values():
            if isinstance(server, str) or isinstance(server, ArtifactoryServer):  # Just URI
                real_servers = True
                break

        with tools.environment_append(self.cache.config.env_vars):
            if real_servers:
                requester = requests.Session()
            else:
                if self.requester_class:
                    requester = self.requester_class(self.servers)
                else:
                    requester = TestRequester(self.servers)

            self.requester = ConanRequester(requester, self.cache,
                                            get_request_timeout())

            self.hook_manager = HookManager(self.cache.hooks_path,
                                            get_env("CONAN_HOOKS", list()), self.user_io.out)

            self.localdb, self.rest_api_client, self.remote_manager = \
                Conan.instance_remote_manager(self.requester, self.cache,
                                              self.user_io, self.hook_manager)
            return output, self.requester

    def init_dynamic_vars(self, user_io=None):
        # Migration system
        self.cache = migrate_and_get_cache(self.base_folder, TestBufferConanOutput(),
                                           storage_folder=self.storage_folder)

        # Maybe something have changed with migrations
        return self._init_collaborators(user_io)

    def run(self, command_line, user_io=None, assert_error=False):
        """ run a single command as in the command line.
            If user or password is filled, user_io will be mocked to return this
            tuple if required
        """
        output, requester = self.init_dynamic_vars(user_io)
        with tools.environment_append(self.cache.config.env_vars):
            # Settings preprocessor
            interactive = not get_env("CONAN_NON_INTERACTIVE", False)
            conan = Conan(self.cache, self.user_io, self.runner, self.remote_manager,
                          self.hook_manager, requester, interactive=interactive)
        outputer = CommandOutputer(self.user_io, self.cache)
        command = Command(conan, self.cache, self.user_io, outputer)
        args = shlex.split(command_line)
        current_dir = os.getcwd()
        os.chdir(self.current_folder)
        old_path = sys.path[:]
        sys.path.append(os.path.join(self.cache.conan_folder, "python"))
        old_modules = list(sys.modules.keys())

        old_output, old_requester = set_global_instances(output, requester)
        try:
            error = command.run(args)
        finally:
            set_global_instances(old_output, old_requester)
            sys.path = old_path
            os.chdir(current_dir)
            # Reset sys.modules to its prev state. A .copy() DOES NOT WORK
            added_modules = set(sys.modules).difference(old_modules)
            for added in added_modules:
                sys.modules.pop(added, None)

        if (assert_error and not error) or (not assert_error and error):
            if assert_error:
                msg = " Command succeeded (failure expected): "
            else:
                msg = " Command failed (unexpectedly): "
            exc_message = "\n{header}\n{cmd}\n{output_header}\n{output}\n{output_footer}\n".format(
                header='{:-^80}'.format(msg),
                output_header='{:-^80}'.format(" Output: "),
                output_footer='-'*80,
                cmd=command_line,
                output=self.user_io.out
            )
            raise Exception(exc_message)

        self.all_output += str(self.user_io.out)
        return error

    def run_command(self, command):
        self.all_output += str(self.out)
        self.init_dynamic_vars() # Resets the output
        return self.runner(command, cwd=self.current_folder)

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

    def copy_from_assets(self, origin_folder, assets):
        for asset in assets:
            s = os.path.join(origin_folder, asset)
            d = os.path.join(self.current_folder, asset)
            if os.path.isdir(s):
                shutil.copytree(s, d)
            else:
                shutil.copy2(s, d)


class TurboTestClient(TestClient):

    tmp_json_name = ".tmp_json"

    def __init__(self, *args, **kwargs):
        if "users" not in kwargs:
            from collections import defaultdict
            kwargs["users"] = defaultdict(lambda: [("conan", "password")])

        super(TurboTestClient, self).__init__(*args, **kwargs)

    def export(self, ref, conanfile=None, args=None, assert_error=False):
        conanfile = str(conanfile) if conanfile else str(GenConanfile())
        self.save({"conanfile.py": conanfile})
        self.run("export . {} {}".format(ref.full_repr(), args or ""),
                 assert_error=assert_error)
        rrev = self.cache.package_layout(ref).recipe_revision()
        return ref.copy_with_rev(rrev)

    def create(self, ref, conanfile=None, args=None, assert_error=False):
        conanfile = str(conanfile) if conanfile else str(GenConanfile())
        self.save({"conanfile.py": conanfile})
        self.run("create . {} {} --json {}".format(ref.full_repr(),
                                                   args or "", self.tmp_json_name),
                 assert_error=assert_error)
        rrev = self.cache.package_layout(ref).recipe_revision()
        json_path = os.path.join(self.current_folder, self.tmp_json_name)
        data = json.loads(load(json_path))
        if assert_error:
            return None
        package_id = data["installed"][0]["packages"][0]["id"]
        package_ref = PackageReference(ref, package_id)
        prev = self.cache.package_layout(ref.copy_clear_rev()).package_revision(package_ref)
        return package_ref.copy_with_revs(rrev, prev)

    def upload_all(self, ref, remote=None, args=None, assert_error=False):
        remote = remote or list(self.servers.keys())[0]
        self.run("upload {} -c --all -r {} {}".format(ref.full_repr(), remote, args or ""),
                 assert_error=assert_error)
        if not assert_error:
            remote_rrev, _ = self.servers[remote].server_store.get_last_revision(ref)
            return ref.copy_with_rev(remote_rrev)
        return

    def remove_all(self):
        self.run("remove '*' -f")

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
        json_path = os.path.join(self.current_folder, self.tmp_json_name)
        data = json.loads(load(json_path))
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

    def init_git_repo(self, files=None, branch=None, submodules=None, origin_url=None):
        _, commit = create_local_git_repo(files, branch, submodules, self.current_folder)
        if origin_url:
            self.runner('git remote add origin {}'.format(origin_url), cwd=self.current_folder)
        return commit

    def init_svn_repo(self, subpath, files=None, repo_url=None):
        if not repo_url:
            repo_url = create_remote_svn_repo(temp_folder())
        url, rev = create_local_svn_checkout(files, repo_url, folder=self.current_folder,
                                             rel_project_path=subpath, delete_checkout=False)
        return rev


class GenConanfile(object):
    """
    USAGE:

    x = GenConanfile().with_import("import os").\
        with_setting("os").\
        with_option("shared", [True, False]).\
        with_default_option("shared", True).\
        with_build_msg("holaaa").\
        with_build_msg("adiooos").\
        with_package_file("file.txt", "hola"). \
        with_package_file("file2.txt", "hola").gen()
    """

    def __init__(self):
        self._imports = ["from conans import ConanFile"]
        self._settings = []
        self._options = {}
        self._default_options = {}
        self._package_files = {}
        self._package_files_env = {}
        self._build_messages = []
        self._scm = {}
        self._requirements = []
        self._revision_mode = None

    def with_revision_mode(self, revision_mode):
        self._revision_mode = revision_mode
        return self

    def with_scm(self, scm):
        self._scm = scm
        return self

    def with_requirement(self, ref):
        self._requirements.append(ref)
        return self

    def with_import(self, i):
        if i not in self._imports:
            self._imports.append(i)
        return self

    def with_setting(self, setting):
        self._settings.append(setting)
        return self

    def with_option(self, option_name, values):
        self._options[option_name] = values
        return self

    def with_default_option(self, option_name, value):
        self._default_options[option_name] = value
        return self

    def with_package_file(self, file_name, contents=None, env_var=None):
        if not contents and not env_var:
            raise Exception("Specify contents or env_var")
        self.with_import("from conans import tools")
        if contents:
            self._package_files[file_name] = contents
        if env_var:
            self.with_import("import os")
            self._package_files_env[file_name] = env_var
        return self

    def with_build_msg(self, msg):
        self._build_messages.append(msg)
        return self

    @property
    def _scm_line(self):
        if not self._scm:
            return ""
        line = ", ".join('"%s": "%s"' % (k, v) for k, v in self._scm.items())
        return "scm = {%s}" % line

    @property
    def _revision_mode_line(self):
        if not self._revision_mode:
            return ""
        line = "revision_mode=\"{}\"".format(self._revision_mode)
        return line

    @property
    def _settings_line(self):
        if not self._settings:
            return ""
        line = ", ".join('"%s"' % s for s in self._settings)
        return "settings = {}".format(line)

    @property
    def _options_line(self):
        if not self._options:
            return ""
        line = ", ".join('"%s": %s' % (k, v) for k, v in self._options.items())
        tmp = "options = {%s}" % line
        if self._default_options:
            line = ", ".join('"%s": %s' % (k, v) for k, v in self._default_options.items())
            tmp += "\n    default_options = {%s}" % line
        return tmp

    @property
    def _requirements_line(self):
        if not self._requirements:
            return ""
        line = ", ".join(['"{}"'.format(r.full_repr()) for r in self._requirements])
        tmp = "requires = %s" % line
        return tmp

    @property
    def _package_method(self):
        lines = []
        if self._package_files:
            lines = ['        tools.save(os.path.join(self.package_folder, "{}"), "{}")'
                     ''.format(key, value)
                     for key, value in self._package_files.items()]

        if self._package_files_env:
            lines.extend(['        tools.save(os.path.join(self.package_folder, "{}"), '
                          'os.getenv("{}"))'.format(key, value)
                          for key, value in self._package_files_env.items()])

        if not lines:
            return ""
        return """
    def package(self):
{}
    """.format("\n".join(lines))

    @property
    def _build_method(self):
        if not self._build_messages:
            return ""
        lines = ['        self.output.warn("{}")'.format(m) for m in self._build_messages]
        return """
    def build(self):
{}
    """.format("\n".join(lines))

    def __repr__(self):
        ret = []
        ret.extend(self._imports)
        ret.append("class HelloConan(ConanFile):")
        if self._requirements_line:
            ret.append("    {}".format(self._requirements_line))
        if self._scm:
            ret.append("    {}".format(self._scm_line))
        if self._revision_mode_line:
            ret.append("    {}".format(self._revision_mode_line))
        if self._settings_line:
            ret.append("    {}".format(self._settings_line))
        if self._options_line:
            ret.append("    {}".format(self._options_line))
        if self._build_method:
            ret.append("    {}".format(self._build_method))
        if self._package_method:
            ret.append("    {}".format(self._package_method))
        if len(ret) == 2:
            ret.append("    pass")
        return "\n".join(ret)


class StoppableThreadBottle(threading.Thread):
    """
    Real server to test download endpoints
    """

    def __init__(self, host=None, port=None):
        self.host = host or "127.0.0.1"
        self.port = port or random.randrange(48000, 49151)
        self.server = bottle.Bottle()
        super(StoppableThreadBottle, self).__init__(target=self.server.run,
                                                    kwargs={"host": self.host, "port": self.port})
        self.daemon = True
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def run_server(self):
        self.start()
        time.sleep(1)
