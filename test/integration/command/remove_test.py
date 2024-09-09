import os
import shutil
import unittest

import pytest

from conan.api.conan_api import ConanAPI
from conans.errors import NotFoundException
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference
from conan.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestClient, TestServer, GenConanfile
from conan.test.utils.env import environment_update

conaninfo = '''
[settings]
    arch=x64
    os=Windows
    compiler=Visual Studio
    compiler.version=8.%s
[options]
    use_Qt=True
[full_requires]
  hello2/0.1@lasote/stable:11111
  OpenSSL/2.10@lasote/testing:2222
  HelloInfo1/0.45@myuser/testing:33333
[recipe_revision]
'''


class TestRemoveWithoutUserChannel:

    @pytest.mark.parametrize("dry_run", [True, False])
    def test_local(self, dry_run):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . --name=lib --version=1.0")
        ref_layout = client.exported_layout()
        pkg_layout = client.created_layout()
        extra = " --dry-run" if dry_run else ""
        client.run("remove lib/1.0 -c" + extra)
        assert os.path.exists(ref_layout.base_folder) == dry_run
        assert os.path.exists(pkg_layout.base_folder) == dry_run

    @pytest.mark.parametrize("confirm", [True, False])
    def test_local_dryrun_output(self, confirm):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . --name=lib --version=1.0")
        client.run("remove lib/1.0 --dry-run", inputs=["yes" if confirm else "no"])
        assert "(yes/no)" in client.out  # Users are asked even when dry-run is set
        if confirm:
            assert "Removed recipe and all binaries" in client.out  # Output it printed for dry-run
        else:
            assert "Removed recipe and all binaries" not in client.out
        print()

    @pytest.mark.artifactory_ready
    def test_remote(self):
        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . --name=lib --version=1.0")
        client.run("upload lib/1.0 -r default -c")
        client.run("remove lib/1.0 -c")
        # we can still install it
        client.run("install --requires=lib/1.0@")
        assert "lib/1.0: Retrieving package" in client.out
        client.run("remove lib/1.0 -c")

        # Now remove remotely, dry run first
        client.run("remove lib/1.0 -c -r default --dry-run")

        # we can still install it
        client.run("install --requires=lib/1.0@")
        assert "lib/1.0: Retrieving package" in client.out
        client.run("remove lib/1.0 -c")

        # Now remove remotely, for real this time
        client.run("remove lib/1.0 -c -r default")

        client.run("install --requires=lib/1.0@", assert_error=True)
        assert "Unable to find 'lib/1.0' in remotes" in client.out


class RemovePackageRevisionsTest(unittest.TestCase):

    NO_SETTINGS_RREF = "4d670581ccb765839f2239cc8dff8fbd"

    def setUp(self):
        self.test_server = TestServer(users={"admin": "password"},
                                      write_permissions=[("foobar/0.1@*/*", "admin")])
        servers = {"default": self.test_server}
        self.client = TestClient(servers=servers, inputs=["admin", "password"])
        ref = RecipeReference.loads(f"foobar/0.1@user/testing#{self.NO_SETTINGS_RREF}")
        self.pref = PkgReference(ref, NO_SETTINGS_PACKAGE_ID, "0ba8627bd47edc3a501e8f0eb9a79e5e")

    def test_remove_local_package_id_argument(self):
        """ Remove package ID based on recipe revision. The package must be deleted, but
            the recipe must be preserved
            Package ID is a separated argument: <package>#<rref> -p <pkgid>
        """
        self.client.save({"conanfile.py": GenConanfile()})
        self.client.run("create . --name=foobar --version=0.1 --user=user --channel=testing")
        assert self.client.package_exists(self.pref)

        self.client.run("remove -c foobar/0.1@user/testing#{}:{}"
                        .format(self.NO_SETTINGS_RREF, NO_SETTINGS_PACKAGE_ID))
        assert not self.client.package_exists(self.pref)

    def test_remove_local_package_id_reference(self):
        """ Remove package ID based on recipe revision. The package must be deleted, but
            the recipe must be preserved.
            Package ID is part of package reference: <package>#<rref>:<pkgid>
        """
        self.client.save({"conanfile.py": GenConanfile()})
        self.client.run("create . --name=foobar --version=0.1 --user=user --channel=testing")
        assert self.client.package_exists(self.pref)

        self.client.run("remove -c foobar/0.1@user/testing#{}:{}"
                        .format(self.NO_SETTINGS_RREF, NO_SETTINGS_PACKAGE_ID))
        assert not self.client.package_exists(self.pref)

    @pytest.mark.artifactory_ready
    def test_remove_remote_package_id_reference(self):
        """ Remove remote package ID based on recipe revision. The package must be deleted, but
            the recipe must be preserved.
            Package ID is part of package reference: <package>#<rref>:<pkgid>
        """
        self.client.save({"conanfile.py": GenConanfile()})
        self.client.run("create . --name=foobar --version=0.1 --user=user --channel=testing")
        self.client.run("upload foobar/0.1@user/testing -r default -c")
        self.client.run("remove -c foobar/0.1@user/testing#{}:{}"
                        .format(self.NO_SETTINGS_RREF, NO_SETTINGS_PACKAGE_ID))
        assert not self.client.package_exists(self.pref)
        self.client.run("remove -c foobar/0.1@user/testing#{}:{} -r default"
                        .format(self.NO_SETTINGS_RREF, NO_SETTINGS_PACKAGE_ID))
        assert not self.client.package_exists(self.pref)

    @pytest.mark.artifactory_ready
    def test_remove_all_packages_but_the_recipe_at_remote(self):
        """ Remove all the packages but not the recipe in a remote
        """
        self.client.save({"conanfile.py": GenConanfile("foobar", "0.1").with_settings("arch")})
        self.client.run("create . --user=user --channel=testing")
        self.client.run("create . --user=user --channel=testing -s arch=x86")
        self.client.run("upload foobar/0.1@user/testing -r default -c")
        ref = self.client.cache.get_latest_recipe_reference(
               RecipeReference.loads("foobar/0.1@user/testing"))
        self.client.run("list foobar/0.1@user/testing#{}:* -r default".format(ref.revision))
        default_arch = self.client.get_default_host_profile().settings['arch']
        self.assertIn(f"arch: {default_arch}", self.client.out)
        self.assertIn("arch: x86", self.client.out)

        self.client.run("remove -c foobar/0.1@user/testing:* -r default")
        self.client.run("search foobar/0.1@user/testing -r default")
        self.assertNotIn(f"arch: {default_arch}", self.client.out)
        self.assertNotIn("arch: x86", self.client.out)


# populated packages of bar
bar_rrev = "bar/1.1#7db54b020cc95b8bdce49cd6aa5623c0"
bar_rrev2 = "bar/1.1#78b42a981b29d2cb00fda10b72f1e72a"
pkg_id_debug = "9e186f6d94c008b544af1569d1a6368d8339efc5"
pkg_id_release = "efa83b160a55b033c4ea706ddb980cd708e3ba1b"
bar_rrev2_debug = '{}:{}'.format(bar_rrev2, pkg_id_debug)
bar_rrev2_release = '{}:{}'.format(bar_rrev2, pkg_id_release)

bar_prev1 = "ee1ca5821b390a75d7168f4567f9ba75"
bar_prev2 = "f523273047249d5a136fe48d33f645bb"
bar_rrev2_release_prev1 = "{}#{}".format(bar_rrev2_release, bar_prev1)
bar_rrev2_release_prev2 = "{}#{}".format(bar_rrev2_release, bar_prev2)


@pytest.fixture(scope="module")
def _populated_client_base():
    """
    foo/1.0@ (one revision) no packages
    foo/1.0@user/channel (one revision)  no packages
    fbar/1.1@ (one revision)  no packages

    bar/1.0@ (two revision) => Debug, Release => (two package revision each)
    """
    # To generate different package revisions
    package_lines = 'save(self, os.path.join(self.package_folder, "foo.txt"), ' \
                    'os.getenv("foo_test", "Na"))'
    client = TestClient(default_server_user=True)
    conanfile = str(GenConanfile().with_settings("build_type")
                                  .with_package(package_lines)
                                  .with_import("from conan.tools.files import save")
                                  .with_import("import os")
                                  .with_import("import time"))
    client.save({"conanfile.py": conanfile})
    client.run("export . --name foo --version 1.0")
    client.run("export . --name foo --version 1.0 --user user --channel channel")
    client.run("export . --name fbar --version 1.1")

    # Two package revisions for bar/1.1 (Release)
    for _i in range(2):
        with environment_update({'foo_test': str(_i)}):
            client.run("create . --name=bar --version=1.1 -s build_type=Release")
    client.run("create . --name=bar --version=1.1 -s build_type=Debug")

    prefs = _get_revisions_packages(client, bar_rrev2_release, False)
    assert set(prefs) == {bar_rrev2_release_prev1, bar_rrev2_release_prev2}

    # Two recipe revisions for bar/1.1
    client.save({"conanfile.py": conanfile + "\n # THIS IS ANOTHER RECIPE REVISION"})
    client.run("create . --name=bar --version=1.1 -s build_type=Debug")

    client.run("upload '*#*:*#*' -c -r default")

    return client


@pytest.fixture()
def populated_client(_populated_client_base):
    """ this is much faster than creating and uploading everythin
    """
    client = TestClient(default_server_user=True)
    shutil.rmtree(client.cache_folder)
    shutil.copytree(_populated_client_base.cache_folder, client.cache_folder)
    shutil.rmtree(client.servers["default"].test_server._base_path)
    shutil.copytree(_populated_client_base.servers["default"].test_server._base_path,
                    client.servers["default"].test_server._base_path)
    client.update_servers()
    return client


@pytest.mark.parametrize("with_remote", [True, False])
@pytest.mark.parametrize("data", [
    {"remove": "foo*", "recipes": ['bar/1.1', 'fbar/1.1']},
    {"remove": "foo/*", "recipes": ['bar/1.1', 'fbar/1.1']},
    {"remove": "*", "recipes": []},
    {"remove": "*/*", "recipes": []},
    {"remove": "*/*#*", "recipes": []},
    {"remove": "*/*#z*", "recipes": ['foo/1.0@user/channel', 'foo/1.0', 'bar/1.1', 'fbar/1.1']},
    {"remove": "f*", "recipes": ["bar/1.1"]},
    {"remove": "*/1.1", "recipes": ["foo/1.0", "foo/1.0@user/channel"]},
    {"remove": "*/*@user/*", "recipes": ["foo/1.0", "fbar/1.1", "bar/1.1"]},
    {"remove": "*/*@*", "recipes": ['foo/1.0', 'fbar/1.1', 'bar/1.1']},
    {"remove": "*/*#*:*", "recipes": ['bar/1.1', 'foo/1.0@user/channel', 'foo/1.0', 'fbar/1.1']},
    {"remove": "foo/1.0@user/channel:*", "recipes": ['bar/1.1', 'foo/1.0@user/channel', 'foo/1.0',
                                                     'fbar/1.1']},
    {"remove": "foo/*@", "recipes": ['foo/1.0@user/channel', 'bar/1.1', 'fbar/1.1']},
    {"remove": "foo", "recipes": ['bar/1.1', 'fbar/1.1']},
    {"remove": "*#", "recipes": []},
    {"remove": "*/*#", "recipes": []},
])
def test_new_remove_recipes_expressions(populated_client, with_remote, data):
    r = "-r default" if with_remote else ""
    error = data.get("error", False)
    populated_client.run("remove {} -c {}".format(data["remove"], r), assert_error=error)
    if not error:
        assert _get_all_recipes(populated_client, with_remote) == set(data["recipes"])
    elif data.get("error_msg"):
        assert data.get("error_msg") in populated_client.out


@pytest.mark.parametrize("with_remote", [True, False])
@pytest.mark.parametrize("data", [
    {"remove": "bar/*#*", "rrevs": []},
    {"remove": "bar/1.1#z*", "rrevs": [bar_rrev, bar_rrev2]},
    {"remove": "bar/1.1#*9*", "rrevs": []},
    {"remove": "bar/1.1#*2a", "rrevs": [bar_rrev]},
    {"remove": "bar*#*50", "rrevs": [bar_rrev, bar_rrev2]},
    {"remove": "bar*#latest", "rrevs": [bar_rrev2]},  # latest is bar_rrev
    {"remove": "bar*#!latest", "rrevs": [bar_rrev]},  # latest is bar_rrev
    {"remove": "bar*#~latest", "rrevs": [bar_rrev]},  # latest is bar_rrev
])
def test_new_remove_recipe_revisions_expressions(populated_client, with_remote, data):
    r = "-r default" if with_remote else ""
    error = data.get("error", False)
    populated_client.run("remove {} -c {}".format(data["remove"], r), assert_error=error)
    if not error:
        rrevs = _get_revisions_recipes(populated_client, "bar/1.1", with_remote)
        assert rrevs == set(data["rrevs"])


@pytest.mark.parametrize("with_remote", [True, False])
@pytest.mark.parametrize("data", [
    {"remove": "bar/1.1#*:*", "prefs": []},
    {"remove": "bar/1.1#*:*#*", "prefs": []},
    {"remove": "bar/1.1#z*:*", "prefs": [bar_rrev2_debug, bar_rrev2_release]},
    {"remove": "bar/1.1#*:*#kk*", "prefs": [bar_rrev2_debug, bar_rrev2_release]},
    {"remove": "bar/1.1#*:{}*".format(pkg_id_release), "prefs": [bar_rrev2_debug]},
    {"remove": "bar/1.1#*:*{}".format(pkg_id_release[-12:]), "prefs": [bar_rrev2_debug]},
    {"remove": "{}:*{}*".format(bar_rrev2, pkg_id_debug[5:15]), "prefs": [bar_rrev2_release]},
    {"remove": "*/*#*:*{}*".format(pkg_id_debug[5:15]), "prefs": [bar_rrev2_release]},
    {"remove": '*/*#*:* -p build_type="fake"', "prefs": [bar_rrev2_release, bar_rrev2_debug]},
    {"remove": '*/*#*:* -p build_type="Release"', "prefs": [bar_rrev2_debug]},
    {"remove": '*/*#*:* -p build_type="Debug"', "prefs": [bar_rrev2_release]},
    # Errors
    {"remove": '*/*#*:*#* -p', "error": True,
     "error_msg": "argument -p/--package-query: expected one argument"},
    {"remove": "bar/1.1#*:", "prefs": []},
    {"remove": "bar/1.1#*:234234*#", "prefs": [bar_rrev2_debug, bar_rrev2_release]},
    {"remove": "bar/1.1:234234*", "prefs": [bar_rrev2_debug, bar_rrev2_release]},
    {"remove": "bar/1.1:* -p os=Windows", "prefs": [bar_rrev2_debug, bar_rrev2_release]},
])
def test_new_remove_package_expressions(populated_client, with_remote, data):
    # Remove the ones we are not testing here
    r = "-r default" if with_remote else ""
    pids = _get_all_packages(populated_client, bar_rrev2, with_remote)
    assert pids == {bar_rrev2_debug, bar_rrev2_release}

    error = data.get("error", False)
    populated_client.run("remove {} -c {}".format(data["remove"], r), assert_error=error)
    if not error:
        pids = _get_all_packages(populated_client, bar_rrev2, with_remote)
        assert pids == set(data["prefs"])
    elif data.get("error_msg"):
        assert data.get("error_msg") in populated_client.out


@pytest.mark.parametrize("with_remote", [True, False])
@pytest.mark.parametrize("data", [
    {"remove": '{}#*kk*'.format(bar_rrev2_release), "prevs": [bar_rrev2_release_prev1,
                                                              bar_rrev2_release_prev2]},
    {"remove": '{}#*'.format(bar_rrev2_release), "prevs": []},
    {"remove": '{}*#{}* -p "build_type=Debug"'.format(bar_rrev2_release, bar_prev2[:3]),
     "prevs": [bar_rrev2_release_prev1, bar_rrev2_release_prev2]},
    {"remove": '{}*#{}* -p "build_type=Release"'.format(bar_rrev2_release, bar_prev2[:3]),
     "prevs": [bar_rrev2_release_prev1]},
    {"remove": '{}*#* -p "build_type=Release"'.format(bar_rrev2_release), "prevs": []},
    {"remove": '{}*#* -p "build_type=Debug"'.format(bar_rrev2_release),
     "prevs": [bar_rrev2_release_prev1, bar_rrev2_release_prev2]},
    # Errors
    {"remove": '{}#'.format(bar_rrev2_release), "prevs": []},
    {"remove": '{}#latest'.format(bar_rrev2_release), "prevs": [bar_rrev2_release_prev1]},
    {"remove": '{}#!latest'.format(bar_rrev2_release), "prevs": [bar_rrev2_release_prev2]},
    {"remove": '{}#~latest'.format(bar_rrev2_release), "prevs": [bar_rrev2_release_prev2]},
])
def test_new_remove_package_revisions_expressions(populated_client, with_remote, data):
    # Remove the ones we are not testing here
    r = "-r default" if with_remote else ""
    populated_client.run("remove f/* -c {}".format(r))

    prefs = _get_revisions_packages(populated_client, bar_rrev2_release, with_remote)
    assert set(prefs) == {bar_rrev2_release_prev1, bar_rrev2_release_prev2}

    error = data.get("error", False)
    populated_client.run("remove {} -c {}".format(data["remove"], r), assert_error=error)
    if not error:
        prefs = _get_revisions_packages(populated_client, bar_rrev2_release, with_remote)
        assert set(prefs) == set(data["prevs"])
    elif data.get("error_msg"):
        assert data.get("error_msg") in populated_client.out


def test_package_query_no_package_ref(populated_client):
    populated_client.run("remove * -p 'compiler=clang'", assert_error=True)
    assert "--package-query supplied but the pattern does not match packages" in populated_client.out


def _get_all_recipes(client, with_remote):
    api = ConanAPI(client.cache_folder)
    remote = api.remotes.get("default") if with_remote else None
    with client.mocked_servers():
        return set([r.repr_notime() for r in api.search.recipes("*", remote=remote)])


def _get_all_packages(client, ref, with_remote):
    ref = RecipeReference.loads(ref)
    api = ConanAPI(client.cache_folder)
    remote = api.remotes.get("default") if with_remote else None
    with client.mocked_servers():
        try:
            return set([r.repr_notime() for r in api.list.packages_configurations(ref, remote=remote)])
        except NotFoundException:
            return set()


def _get_revisions_recipes(client, ref, with_remote):
    ref = RecipeReference.loads(ref)
    api = ConanAPI(client.cache_folder)
    remote = api.remotes.get("default") if with_remote else None
    with client.mocked_servers():
        try:
            return set([r.repr_notime() for r in api.list.recipe_revisions(ref, remote=remote)])
        except NotFoundException:
            return set()


def _get_revisions_packages(client, pref, with_remote):
    pref = PkgReference.loads(pref)
    api = ConanAPI(client.cache_folder)
    remote = api.remotes.get("default") if with_remote else None
    with client.mocked_servers():
        try:
            return set([r.repr_notime() for r in api.list.package_revisions(pref, remote=remote)])
        except NotFoundException:
            return set()
