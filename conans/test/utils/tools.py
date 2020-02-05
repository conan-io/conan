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
import unittest
import uuid
from collections import Counter, OrderedDict
from contextlib import contextmanager

import bottle
import requests
import six
import time
from mock import Mock
from six import StringIO
from six.moves.urllib.parse import quote, urlsplit, urlunsplit
from webtest.app import TestApp
from requests.exceptions import HTTPError

from conans import load
from conans.client.cache.cache import ClientCache
from conans.client.cache.remote_registry import Remotes
from conans.client.command import Command
from conans.client.conan_api import Conan
from conans.client.output import ConanOutput
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
from conans.test.utils.server_launcher import (TESTING_REMOTE_PRIVATE_PASS,
                                               TESTING_REMOTE_PRIVATE_USER,
                                               TestServerLauncher)
from conans.test.utils.test_files import temp_folder
from conans.util.env_reader import get_env
from conans.util.files import mkdir, save_files
from conans.client.runner import ConanRunner
from conans.util.runners import check_output_runner

NO_SETTINGS_PACKAGE_ID = "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9"

ARTIFACTORY_DEFAULT_USER = os.getenv("ARTIFACTORY_DEFAULT_USER", "admin")
ARTIFACTORY_DEFAULT_PASSWORD = os.getenv("ARTIFACTORY_DEFAULT_PASSWORD", "password")
ARTIFACTORY_DEFAULT_URL = os.getenv("ARTIFACTORY_DEFAULT_URL", "http://localhost:8090/artifactory")


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


def test_profile(profile=None, settings=None):
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

    def __init__(self, *args, **kwargs):
        self._user = ARTIFACTORY_DEFAULT_USER
        self._password = ARTIFACTORY_DEFAULT_PASSWORD
        self._url = ARTIFACTORY_DEFAULT_URL
        self._repo_name = "conan_{}".format(str(uuid.uuid4()).replace("-", ""))
        self.create_repository()
        self.server_store = ArtifactoryServerStore(self.repo_url, self._user, self._password)

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


class TestBufferConanOutput(ConanOutput):
    """ wraps the normal output of the application, captures it into an stream
    and gives it operators similar to string, so it can be compared in tests
    """

    def __init__(self):
        ConanOutput.__init__(self, StringIO(), color=False)

    def __repr__(self):
        # FIXME: I'm sure there is a better approach. Look at six docs.
        if six.PY2:
            return str(self._stream.getvalue().encode("ascii", "ignore"))
        else:
            return self._stream.getvalue()

    def __str__(self, *args, **kwargs):
        return self.__repr__()

    def __eq__(self, value):
        return self.__repr__() == value

    def __ne__(self, value):
        return not self.__eq__(value)

    def __contains__(self, value):
        return value in self.__repr__()


def create_local_git_repo(files=None, branch=None, submodules=None, folder=None, commits=1, tags=None):
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
    for i in range(0, commits):
        git.run('commit --allow-empty -m "commiting"')

    tags = tags or []
    for tag in tags:
        git.run("tag %s" % tag)

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
                rev = check_output_runner("svn info --show-item revision").strip()
            else:
                import xml.etree.ElementTree as ET
                output = check_output_runner("svn info --xml").strip()
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


class LocalDBMock(object):

    def __init__(self, user=None, access_token=None, refresh_token=None):
        self.user = user
        self.access_token = access_token
        self.refresh_token = refresh_token

    def get_login(self, _):
        return self.user, self.access_token, self.refresh_token

    def get_username(self, _):
        return self.user

    def store(self, user, access_token, refresh_token, _):
        self.user = user
        self.access_token = access_token
        self.refresh_token = refresh_token


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

    def __init__(self, cache_folder=None, current_folder=None, servers=None, users=None,
                 requester_class=None, runner=None, path_with_spaces=True,
                 revisions_enabled=None, cpu_count=1, default_server_user=None):
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
            server = TestServer(users=server_users)
            servers = {"default": server}

        self.users = users
        if self.users is None:
            self.users = {"default": [(TESTING_REMOTE_PRIVATE_USER, TESTING_REMOTE_PRIVATE_PASS)]}

        self.cache_folder = cache_folder or temp_folder(path_with_spaces)
        self.requester_class = requester_class
        self.runner = runner

        if revisions_enabled is None:
            revisions_enabled = get_env("TESTING_REVISIONS_ENABLED", False)

        self.tune_conan_conf(cache_folder, cpu_count, revisions_enabled)

        if servers and len(servers) > 1 and not isinstance(servers, OrderedDict):
            raise Exception("""Testing framework error: Servers should be an OrderedDict. e.g:
servers = OrderedDict()
servers["r1"] = server
servers["r2"] = TestServer()
""")

        self.servers = servers or {}
        if servers is not False:  # Do not mess with registry remotes
            self.update_servers()
        self.current_folder = current_folder or temp_folder(path_with_spaces)

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
        current_conf = load(self.cache.conan_conf_path)
        if "revisions_enabled" in current_conf:  # Invalidate any previous value to be sure
            replace_in_file(self.cache.conan_conf_path, "revisions_enabled", "#revisions_enabled",
                            output=TestBufferConanOutput())

        replace_in_file(self.cache.conan_conf_path,
                        "[general]", "[general]\nrevisions_enabled = %s" % value,
                        output=TestBufferConanOutput())

    def enable_revisions(self):
        self._set_revisions("1")
        assert self.cache.config.revisions_enabled

    def disable_revisions(self):
        self._set_revisions("0")
        assert not self.cache.config.revisions_enabled

    def tune_conan_conf(self, cache_folder, cpu_count, revisions_enabled):
        # Create the default
        cache = self.cache
        cache.config

        if cpu_count:
            replace_in_file(cache.conan_conf_path,
                            "# cpu_count = 1", "cpu_count = %s" % cpu_count,
                            output=TestBufferConanOutput(), strict=not bool(cache_folder))

        current_conf = load(cache.conan_conf_path)
        if "revisions_enabled" in current_conf:  # Invalidate any previous value to be sure
            replace_in_file(cache.conan_conf_path, "revisions_enabled", "#revisions_enabled",
                            output=TestBufferConanOutput())
        if revisions_enabled:
            replace_in_file(cache.conan_conf_path,
                            "[general]", "[general]\nrevisions_enabled = 1",
                            output=TestBufferConanOutput())

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

    @property
    def default_compiler_visual_studio(self):
        settings = self.cache.default_profile.settings
        return settings.get("compiler", None) == "Visual Studio"

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

    def get_conan_api(self, user_io=None):
        if user_io:
            self.out = user_io.out
        else:
            self.out = TestBufferConanOutput()
        user_io = user_io or MockedUserIO(self.users, out=self.out)

        conan = Conan(cache_folder=self.cache_folder, output=self.out, user_io=user_io,
                      http_requester=self._http_requester, runner=self.runner)
        return conan

    def run(self, command_line, user_io=None, assert_error=False):
        """ run a single command as in the command line.
            If user or password is filled, user_io will be mocked to return this
            tuple if required
        """
        conan = self.get_conan_api(user_io)
        self.api = conan
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
                output_footer='-'*80,
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

    def copy_from_assets(self, origin_folder, assets):
        for asset in assets:
            s = os.path.join(origin_folder, asset)
            d = os.path.join(self.current_folder, asset)
            if os.path.isdir(s):
                shutil.copytree(s, d)
            else:
                shutil.copy2(s, d)


class GenConanfile(object):
    """
    USAGE:

    x = GenConanfile().with_import("import os").\
        with_setting("os").\
        with_option("shared", [True, False]).\
        with_default_option("shared", True).\
        with_build_msg("holaaa").\
        with_build_msg("adiooos").\
        with_package_file("file.txt", "hola").\
        with_package_file("file2.txt", "hola")
    """

    def __init__(self):
        self._imports = ["from conans import ConanFile"]
        self._name = None
        self._version = None
        self._settings = []
        self._options = {}
        self._generators = []
        self._default_options = {}
        self._package_files = {}
        self._package_files_env = {}
        self._build_messages = []
        self._scm = {}
        self._requires = []
        self._requirements = []
        self._build_requires = []
        self._revision_mode = None
        self._package_info = {}
        self._package_id_lines = []

    def with_name(self, name):
        self._name = name
        return self

    def with_version(self, version):
        self._version = version
        return self

    def with_revision_mode(self, revision_mode):
        self._revision_mode = revision_mode
        return self

    def with_scm(self, scm):
        self._scm = scm
        return self

    def with_generator(self, generator):
        self._generators.append(generator)
        return self

    def with_require(self, ref, private=False, override=False):
        return self.with_require_plain(ref.full_str(), private, override)

    def with_require_plain(self, ref_str, private=False, override=False):
        self._requires.append((ref_str, private, override))
        return self

    def with_requirement(self, ref, private=False, override=False):
        return self.with_requirement_plain(ref.full_str(), private, override)

    def with_requirement_plain(self, ref_str, private=False, override=False):
        self._requirements.append((ref_str, private, override))
        return self

    def with_build_require(self, ref):
        return self.with_build_require_plain(ref.full_str())

    def with_build_require_plain(self, ref_str):
        self._build_requires.append(ref_str)
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
        self.with_import("import os")
        self.with_import("from conans import tools")
        if contents:
            self._package_files[file_name] = contents
        if env_var:
            self._package_files_env[file_name] = env_var
        return self

    def with_build_msg(self, msg):
        self._build_messages.append(msg)
        return self

    def with_package_info(self, cpp_info=None, env_info=None):
        assert isinstance(cpp_info, dict), "cpp_info ({}) expects dict".format(type(cpp_info))
        assert isinstance(env_info, dict), "env_info ({}) expects dict".format(type(env_info))
        if cpp_info:
            self._package_info["cpp_info"] = cpp_info
        if env_info:
            self._package_info["env_info"] = env_info
        return self

    def with_package_id(self, line):
        self._package_id_lines.append(line)
        return self

    @property
    def _name_line(self):
        if not self._name:
            return ""
        return "name = '{}'".format(self._name)

    @property
    def _version_line(self):
        if not self._version:
            return ""
        return "version = '{}'".format(self._version)

    @property
    def _scm_line(self):
        if not self._scm:
            return ""
        line = ", ".join('"%s": "%s"' % (k, v) for k, v in self._scm.items())
        return "scm = {%s}" % line

    @property
    def _generators_line(self):
        if not self._generators:
            return ""
        line = ", ".join('"{}"'.format(generator) for generator in self._generators)
        return "generators = {}".format(line)

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
        return tmp

    @property
    def _default_options_line(self):
        if not self._default_options:
            return ""
        line = ", ".join('"%s": %s' % (k, v) for k, v in self._default_options.items())
        tmp = "default_options = {%s}" % line
        return tmp

    @property
    def _build_requires_line(self):
        if not self._build_requires:
            return ""
        line = ", ".join(['"{}"'.format(r) for r in self._build_requires])
        tmp = "build_requires = %s" % line
        return tmp

    @property
    def _requires_line(self):
        if not self._requires:
            return ""
        items = []
        for ref, private, override in self._requires:
            if private or override:
                private_str = ", 'private'" if private else ""
                override_str = ", 'override'" if override else ""
                items.append('("{}"{}{})'.format(ref, private_str, override_str))
            else:
                items.append('"{}"'.format(ref))
        tmp = "requires = ({}, )".format(", ".join(items))
        return tmp

    @property
    def _requirements_method(self):
        if not self._requirements:
            return ""

        lines = []
        for ref, private, override in self._requirements:
            private_str = ", private=True" if private else ""
            override_str = ", override=True" if override else ""
            lines.append('        self.requires("{}"{}{})'.format(ref, private_str, override_str))

        return """
    def requirements(self):
{}
        """.format("\n".join(lines))

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

    @property
    def _package_info_method(self):
        if not self._package_info:
            return ""
        lines = []
        if "cpp_info" in self._package_info:
            for k, v in self._package_info["cpp_info"].items():
                lines.append('        self.cpp_info.{} = {}'.format(k, str(v)))
        if "env_info" in self._package_info:
            for k, v in self._package_info["env_info"].items():
                lines.append('        self.env_info.{} = {}'.format(k, str(v)))

        return """
    def package_info(self):
{}
        """.format("\n".join(lines))

    @property
    def _package_id_method(self):
        if not self._package_id_lines:
            return ""
        lines = ['        {}'.format(line) for line in self._package_id_lines]
        return """
    def package_id(self):
{}
        """.format("\n".join(lines))

    def __repr__(self):
        ret = []
        ret.extend(self._imports)
        ret.append("class HelloConan(ConanFile):")
        if self._name_line:
            ret.append("    {}".format(self._name_line))
        if self._version_line:
            ret.append("    {}".format(self._version_line))
        if self._generators_line:
            ret.append("    {}".format(self._generators_line))
        if self._requires_line:
            ret.append("    {}".format(self._requires_line))
        if self._requirements_method:
            ret.append("    {}".format(self._requirements_method))
        if self._build_requires_line:
            ret.append("    {}".format(self._build_requires_line))
        if self._scm:
            ret.append("    {}".format(self._scm_line))
        if self._revision_mode_line:
            ret.append("    {}".format(self._revision_mode_line))
        if self._settings_line:
            ret.append("    {}".format(self._settings_line))
        if self._options_line:
            ret.append("    {}".format(self._options_line))
        if self._default_options_line:
            ret.append("    {}".format(self._default_options_line))
        if self._build_method:
            ret.append("    {}".format(self._build_method))
        if self._package_method:
            ret.append("    {}".format(self._package_method))
        if self._package_info_method:
            ret.append("    {}".format(self._package_info_method))
        if self._package_id_lines:
            ret.append("    {}".format(self._package_id_method))
        if len(ret) == 2:
            ret.append("    pass")
        return "\n".join(ret)


class TurboTestClient(TestClient):

    tmp_json_name = ".tmp_json"

    def __init__(self, *args, **kwargs):
        if "users" not in kwargs and "default_server_user" not in kwargs:
            from collections import defaultdict
            kwargs["users"] = defaultdict(lambda: [("conan", "password")])

        super(TurboTestClient, self).__init__(*args, **kwargs)

    def export(self, ref, conanfile=GenConanfile(), args=None, assert_error=False):
        if conanfile:
            self.save({"conanfile.py": conanfile})
        self.run("export . {} {}".format(ref.full_str(), args or ""),
                 assert_error=assert_error)
        rrev = self.cache.package_layout(ref).recipe_revision()
        return ref.copy_with_rev(rrev)

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

    def remove_all(self):
        self.run("remove '*' -f")

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

    def init_git_repo(self, files=None, branch=None, submodules=None, origin_url=None):
        _, commit = create_local_git_repo(files, branch, submodules, self.current_folder)
        if origin_url:
            self.run_command('git remote add origin {}'.format(origin_url))
        return commit

    def init_svn_repo(self, subpath, files=None, repo_url=None):
        if not repo_url:
            repo_url = create_remote_svn_repo(temp_folder())
        _, rev = create_local_svn_checkout(files, repo_url, folder=self.current_folder,
                                           rel_project_path=subpath, delete_checkout=False)
        return rev


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
