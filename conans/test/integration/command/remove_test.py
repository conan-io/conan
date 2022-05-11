import os
import unittest

import pytest

from conan.api.conan_api import ConanAPIV2
from conans.errors import NotFoundException
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference
from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestClient, TestServer, GenConanfile
from conans.util.env import environment_update


class RemoveOutdatedTest(unittest.TestCase):

    @pytest.mark.xfail(reason="Tests using the Search command are temporarely disabled")
    def test_remove_query(self):
        test_server = TestServer(users={"admin": "password"})  # exported users and passwords
        servers = {"default": test_server}
        client = TestClient(servers=servers, inputs=["admin", "password"])
        conanfile = """from conan import ConanFile
class Test(ConanFile):
    settings = "os"
    """
        client.save({"conanfile.py": conanfile})
        client.run("create . --name=Test --version=0.1 --user=lasote --channel=testing -s os=Windows")
        client.run("create . --name=Test --version=0.1 --user=lasote --channel=testing -s os=Linux")
        client.save({"conanfile.py": conanfile.replace("settings", "pass #")})
        client.run("create . --name=Test2 --version=0.1 --user=lasote --channel=testing")
        client.run("upload * --confirm -r default")

        for remote in ("", "-r=default"):
            client.run("remove Test/0.1@lasote/testing -q=os=Windows -f %s" % remote)
            client.run("search Test/0.1@lasote/testing %s" % remote)
            self.assertNotIn("os: Windows", client.out)
            self.assertIn("os: Linux", client.out)

            client.run("remove Test2/0.1@lasote/testing -q=os=Windows -f %s" % remote)
            client.run("search Test2/0.1@lasote/testing %s" % remote)
            self.assertIn("Package_ID: %s" % NO_SETTINGS_PACKAGE_ID, client.out)
            client.run("remove Test2/0.1@lasote/testing -q=os=None -f %s" % remote)
            client.run("search Test2/0.1@lasote/testing %s" % remote)
            self.assertNotIn("Package_ID: %s" % NO_SETTINGS_PACKAGE_ID, client.out)
            self.assertIn("There are no packages", client.out)


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


class RemoveWithoutUserChannel(unittest.TestCase):

    def setUp(self):
        self.test_server = TestServer(users={"lasote": "password"},
                                      write_permissions=[("lib/1.0@*/*", "lasote")])
        servers = {"default": self.test_server}
        self.client = TestClient(servers=servers, inputs=["lasote", "password"])

    def test_local(self):
        self.client.save({"conanfile.py": GenConanfile()})
        self.client.run("create . --name=lib --version=1.0")
        latest_rrev = self.client.cache.get_latest_recipe_reference(RecipeReference.loads("lib/1.0"))
        ref_layout = self.client.cache.ref_layout(latest_rrev)
        pkg_ids = self.client.cache.get_package_references(latest_rrev)
        latest_prev = self.client.cache.get_latest_package_reference(pkg_ids[0])
        pkg_layout = self.client.cache.pkg_layout(latest_prev)
        self.client.run("remove lib/1.0 -f")
        self.assertFalse(os.path.exists(ref_layout.base_folder))
        self.assertFalse(os.path.exists(pkg_layout.base_folder))

    def test_remote(self):
        self.client.save({"conanfile.py": GenConanfile()})
        self.client.run("create . --name=lib --version=1.0")
        self.client.run("upload lib/1.0 -r default -c")
        self.client.run("remove lib/1.0 -f")
        # we can still install it
        self.client.run("install --requires=lib/1.0@")
        self.assertIn("lib/1.0: Retrieving package", self.client.out)
        self.client.run("remove lib/1.0 -f")

        # Now remove remotely
        self.client.run("remove lib/1.0 -f -r default")
        self.client.run("install --requires=lib/1.0@", assert_error=True)

        self.assertIn("Unable to find 'lib/1.0' in remotes", self.client.out)


class RemovePackageRevisionsTest(unittest.TestCase):

    NO_SETTINGS_RREF = "4d670581ccb765839f2239cc8dff8fbd"

    def setUp(self):
        self.test_server = TestServer(users={"user": "password"},
                                      write_permissions=[("foobar/0.1@*/*", "user")])
        servers = {"default": self.test_server}
        self.client = TestClient(servers=servers, inputs=["user", "password"])
        ref = RecipeReference.loads(f"foobar/0.1@user/testing#{self.NO_SETTINGS_RREF}")
        self.pref = PkgReference(ref, NO_SETTINGS_PACKAGE_ID, "871e6d06bd4bbea0172937df1717e075")

    def test_remove_local_package_id_argument(self):
        """ Remove package ID based on recipe revision. The package must be deleted, but
            the recipe must be preserved
            Package ID is a separated argument: <package>#<rref> -p <pkgid>
        """
        self.client.save({"conanfile.py": GenConanfile()})
        self.client.run("create . --name=foobar --version=0.1 --user=user --channel=testing")
        assert self.client.package_exists(self.pref)

        self.client.run("remove -f foobar/0.1@user/testing#{}:{}"
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

        self.client.run("remove -f foobar/0.1@user/testing#{}:{}"
                        .format(self.NO_SETTINGS_RREF, NO_SETTINGS_PACKAGE_ID))
        assert not self.client.package_exists(self.pref)

    def test_remove_remote_package_id_reference(self):
        """ Remove remote package ID based on recipe revision. The package must be deleted, but
            the recipe must be preserved.
            Package ID is part of package reference: <package>#<rref>:<pkgid>
        """
        self.client.save({"conanfile.py": GenConanfile()})
        self.client.run("create . --name=foobar --version=0.1 --user=user --channel=testing")
        self.client.run("upload foobar/0.1@user/testing -r default -c")
        self.client.run("remove -f foobar/0.1@user/testing#{}:{}"
                        .format(self.NO_SETTINGS_RREF, NO_SETTINGS_PACKAGE_ID))
        assert not self.client.package_exists(self.pref)
        self.client.run("remove -f foobar/0.1@user/testing#{}:{} -r default"
                        .format(self.NO_SETTINGS_RREF, NO_SETTINGS_PACKAGE_ID))
        assert not self.client.package_exists(self.pref)

    def test_remove_all_packages_but_the_recipe_at_remote(self):
        """ Remove all the packages but not the recipe in a remote
        """
        self.client.save({"conanfile.py": GenConanfile("foobar", "0.1").with_settings("arch")})
        self.client.run("create . --user=user --channel=testing")
        self.client.run("create . --user=user --channel=testing -s arch=x86")
        self.client.run("upload foobar/0.1@user/testing -r default -c")
        ref = self.client.cache.get_latest_recipe_reference(
               RecipeReference.loads("foobar/0.1@user/testing"))
        self.client.run("list packages foobar/0.1@user/testing#{} -r default".format(ref.revision))
        self.assertIn("arch=x86_64", self.client.out)
        self.assertIn("arch=x86", self.client.out)

        self.client.run("remove -f foobar/0.1@user/testing -p -r default")
        self.client.run("search foobar/0.1@user/testing -r default")
        self.assertNotIn("arch=x86_64", self.client.out)
        self.assertNotIn("arch=x86", self.client.out)


# populated packages of bar
bar_rrev = "bar/1.1#7db54b020cc95b8bdce49cd6aa5623c0"
bar_rrev2 = "bar/1.1#78b42a981b29d2cb00fda10b72f1e72a"
pkg_id_debug = "040ce2bd0189e377b2d15eb7246a4274d1c63317"
pkg_id_release = "e53d55fd33066c49eb97a4ede6cb50cd8036fe8b"
bar_rrev2_debug = '{}:{}'.format(bar_rrev2, pkg_id_debug)
bar_rrev2_release = '{}:{}'.format(bar_rrev2, pkg_id_release)

bar_prev1 = "51ef5374f2df568657c8f5198a77fa4d"
bar_prev2 = "42ff219d456bdf6b29d165e5fb5db7ec"
bar_rrev2_release_prev1 = "{}#{}".format(bar_rrev2_release, bar_prev1)
bar_rrev2_release_prev2 = "{}#{}".format(bar_rrev2_release, bar_prev2)


@pytest.fixture()
def populated_client():
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

    client.run("upload '*' -c -r default")
    # By default only the latest is uploaded, we want all of them
    client.run("upload {} -c -r default".format(bar_rrev))
    client.run("upload {} -c -r default".format(bar_rrev2))
    client.run("upload {} -c -r default".format(bar_rrev2_release_prev1))
    client.run("upload {} -c -r default".format(bar_rrev2_release_prev2))

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
    {"remove": "foo/1.0@user/channel -p", "recipes": ['bar/1.1', 'foo/1.0@user/channel', 'foo/1.0',
                                                      'fbar/1.1']},
    {"remove": "foo/*@", "recipes": ['foo/1.0@user/channel', 'bar/1.1', 'fbar/1.1']},
    # These are errors
    {"remove": "foo", "error": True,
     "error_msg": 'ERROR: Invalid expression, specify a version or a wildcard. e.g: foo*\n'},
    {"remove": "*#", "error": True},
    {"remove": "*/*#", "error": True},
])
def test_new_remove_recipes_expressions(populated_client, with_remote, data):

    with populated_client.mocked_servers():
        r = "-r default" if with_remote else ""
        error = data.get("error", False)
        populated_client.run("remove {} -f {}".format(data["remove"], r), assert_error=error)
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
    {"remove": "bar*#*50", "error": True, "error_msg": "Invalid expression, specify version"},
])
def test_new_remove_recipe_revisions_expressions(populated_client, with_remote, data):
    with populated_client.mocked_servers():
        r = "-r default" if with_remote else ""
        error = data.get("error", False)
        populated_client.run("remove {} -f {}".format(data["remove"], r), assert_error=error)
        if not error:
            rrevs = _get_revisions_recipes(populated_client, "bar/1.1", with_remote)
            assert rrevs == set(data["rrevs"])


@pytest.mark.parametrize("with_remote", [True, False])
@pytest.mark.parametrize("data", [
    {"remove": "bar/1.1#*:*", "prefs": []},
    {"remove": "bar/1.1#*:*#*", "prefs": []},
    {"remove": "bar/1.1#z*:*", "prefs": [bar_rrev2_debug, bar_rrev2_release]},
    {"remove": "bar/1.1#*:*#kk*", "prefs": [bar_rrev2_debug, bar_rrev2_release]},
    {"remove": "bar/1.1#*:{}".format(pkg_id_release), "prefs": [bar_rrev2_debug]},
    {"remove": "bar/1.1#*:*{}".format(pkg_id_release[-12:]), "prefs": [bar_rrev2_debug]},
    {"remove": "{}:*{}*".format(bar_rrev2, pkg_id_debug[5:15]), "prefs": [bar_rrev2_release]},
    {"remove": "*/*#*:*{}*".format(pkg_id_debug[5:15]), "prefs": [bar_rrev2_release]},
    {"remove": '*/*#*:* -p build_type="fake"', "prefs": [bar_rrev2_release, bar_rrev2_debug]},
    {"remove": '*/*#*:* -p build_type="Release"', "prefs": [bar_rrev2_debug]},
    {"remove": '*/*#*:* -p build_type="Debug"', "prefs": [bar_rrev2_release]},
    # Errors
    {"remove": '*/*#*:*#* -p', "error": True,
     "error_msg": "The -p argument cannot be used with a package reference"},
    {"remove": "bar/1.1#*:", "error": True, "error_msg": 'Specify a package ID value'},
    {"remove": "bar/1.1#*:234234#", "error": True, "error_msg": 'Specify a package revision'},
    {"remove": "bar/1.1:234234", "error": True,
     "error_msg": 'ERROR: Specify a recipe revision or a wildcard. e.g: bar/1.1#*\n'},
    {"remove": "bar/1.1 -p os=Windows", "error": True,
     "error_msg": 'ERROR: Specify a recipe revision or a wildcard. e.g: bar/1.1#*\n'},
])
def test_new_remove_package_expressions(populated_client, with_remote, data):
    # Remove the ones we are not testing here
    r = "-r default" if with_remote else ""
    populated_client.run("remove f/* -f {}".format(r))

    pids = _get_all_packages(populated_client, bar_rrev2, with_remote)
    assert pids == {bar_rrev2_debug, bar_rrev2_release}

    with populated_client.mocked_servers():
        error = data.get("error", False)
        populated_client.run("remove {} -f {}".format(data["remove"], r), assert_error=error)
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
    {"remove": '{}#{}* -p "build_type=Debug"'.format(bar_rrev2_release, bar_prev2[:3]),
     "prevs": [bar_rrev2_release_prev1, bar_rrev2_release_prev2]},
    {"remove": '{}#{}* -p "build_type=Release"'.format(bar_rrev2_release, bar_prev2[:3]),
     "prevs": [bar_rrev2_release_prev1]},
    {"remove": '{}#* -p "build_type=Release"'.format(bar_rrev2_release), "prevs": []},
    {"remove": '{}#* -p "build_type=Debug"'.format(bar_rrev2_release),
     "prevs": [bar_rrev2_release_prev1, bar_rrev2_release_prev2]},
    # Errors
    {"remove": '{}#'.format(bar_rrev2_release), "error": True,
     "error_msg": "Specify a package revision"},
])
def test_new_remove_package_revisions_expressions(populated_client, with_remote, data):
    # Remove the ones we are not testing here
    r = "-r default" if with_remote else ""
    populated_client.run("remove f/* -f {}".format(r))

    prefs = _get_revisions_packages(populated_client, bar_rrev2_release, with_remote)
    assert set(prefs) == {bar_rrev2_release_prev1, bar_rrev2_release_prev2}

    with populated_client.mocked_servers():
        error = data.get("error", False)
        populated_client.run("remove {} -f {}".format(data["remove"], r), assert_error=error)
        if not error:
            prefs = _get_revisions_packages(populated_client, bar_rrev2_release, with_remote)
            assert set(prefs) == set(data["prevs"])
        elif data.get("error_msg"):
            assert data.get("error_msg") in populated_client.out


def _get_all_recipes(client, with_remote):
    api = ConanAPIV2(client.cache_folder)
    remote = api.remotes.get("default") if with_remote else None
    with client.mocked_servers():
        return set([r.repr_notime() for r in api.search.recipes("*", remote=remote)])


def _get_all_packages(client, ref, with_remote):
    ref = RecipeReference.loads(ref)
    api = ConanAPIV2(client.cache_folder)
    remote = api.remotes.get("default") if with_remote else None
    with client.mocked_servers():
        try:
            return set([r.repr_notime() for r in api.list.packages_configurations(ref, remote=remote)])
        except NotFoundException:
            return set()


def _get_revisions_recipes(client, ref, with_remote):
    ref = RecipeReference.loads(ref)
    api = ConanAPIV2(client.cache_folder)
    remote = api.remotes.get("default") if with_remote else None
    with client.mocked_servers():
        try:
            return set([r.repr_notime() for r in api.list.recipe_revisions(ref, remote=remote)])
        except NotFoundException:
            return set()


def _get_revisions_packages(client, pref, with_remote):
    pref = PkgReference.loads(pref)
    api = ConanAPIV2(client.cache_folder)
    remote = api.remotes.get("default") if with_remote else None
    with client.mocked_servers():
        try:
            return set([r.repr_notime() for r in api.list.package_revisions(pref, remote=remote)])
        except NotFoundException:
            return set()

