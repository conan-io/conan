"""
Scenario from https://github.com/conan-io/conan/issues/20527

Build every third-party dependency (those without user/channel, e.g. ConanCenter recipes) in
Release, while our own packages (with user/channel) and the "consumer" follow the requested
``build_type``.

The natural way to express it is a ``*@:build_type=Release`` settings pattern, but ``*@`` also
matches the consumer (a consumer has no user/channel), so the consumer is silently forced to
Release too. The ``&`` consumer pattern can only assign a fixed value, it cannot say "follow the
requested one", and there is no way to exclude the consumer from a ``*@`` pattern.

The most problematic case is ``conan create``, where several things are "the consumer": the
package being created and the ``test_package`` conanfile. With ``--user/--channel`` the created
package follows the requested ``build_type``, but the ``test_package`` (no user/channel) does not,
so a Debug package is tested with a Release ``test_package``.
"""
import json
import textwrap

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def _build_types(client):
    """ {name: build_type} of the nodes of the graph (json output) of the last client run.
    The root node (consumer or test_package) has no name and it is reported as "root" """
    nodes = json.loads(client.stdout)["graph"]["nodes"].values()
    return {n["name"] or "root": n["settings"]["build_type"] for n in nodes}


@pytest.fixture()
def client():
    """
    zlib/1.0, openssl/1.0     -> "ConanCenter" like, no user/channel
    mylib/1.0@company/stable  -> our own package, depends on openssl
    """
    c = TestClient()
    c.save({"zlib/conanfile.py": GenConanfile("zlib", "1.0").with_settings("build_type"),
            "openssl/conanfile.py": GenConanfile("openssl", "1.0").with_settings("build_type")
                                                                  .with_requires("zlib/1.0"),
            "mylib/conanfile.py": GenConanfile("mylib", "1.0").with_settings("build_type")
                                                              .with_requires("openssl/1.0"),
            "profile": textwrap.dedent("""\
                [settings]
                build_type=Debug
                # all dependencies without user/channel always in Release
                *@:build_type=Release
                """)})
    c.run("export zlib")
    c.run("export openssl")
    c.run("export mylib --user=company --channel=stable")
    return c


def test_third_party_in_release_own_packages_follow(client):
    """ This is the part of the request that is possible: no user/channel always Release,
    including new dependencies added later, and user/channel packages follow the requested one
    """
    client.save({"consumer/conanfile.py": GenConanfile().with_settings("build_type")
                                                        .with_requires("mylib/1.0@company/stable")})
    client.run("graph info consumer -pr=profile --format=json")
    bt = _build_types(client)
    assert bt["zlib"] == "Release"
    assert bt["openssl"] == "Release"
    assert bt["mylib"] == "Debug"


def test_consumer_conanfile_py_name(client):
    client.save({"app/conanfile.py": GenConanfile("app").with_settings("build_type")
                                                        .with_requires("mylib/1.0@company/stable")})
    client.run("graph info app -pr=profile --format=json")
    bt = _build_types(client)
    assert bt["zlib"] == "Release"
    assert bt["openssl"] == "Release"
    assert bt["mylib"] == "Debug"
    # Consumer has a name and channel, so it is Release
    assert bt["app"] == "Release"

    client.run("graph info app --user=myuser -pr=profile --format=json")
    bt = _build_types(client)
    assert bt["zlib"] == "Release"
    assert bt["openssl"] == "Release"
    assert bt["mylib"] == "Debug"
    # Consumer has a name and user, so it is Debug
    assert bt["app"] == "Debug"


def test_consumer_conanfile_py_no_name(client):
    client.save({"app/conanfile.py": GenConanfile().with_settings("build_type")
                                                   .with_requires("mylib/1.0@company/stable")})
    client.run("graph info app -pr=profile --format=json")
    bt = _build_types(client)
    assert bt["zlib"] == "Release"
    assert bt["openssl"] == "Release"
    assert bt["mylib"] == "Debug"
    # Consumer doesn't have a name, always Debug
    assert bt["root"] == "Debug"

    client.run("graph info app --user=myuser -pr=profile --format=json")
    bt = _build_types(client)
    assert bt["zlib"] == "Release"
    assert bt["openssl"] == "Release"
    assert bt["mylib"] == "Debug"
    # Consumer doesn't have a name, always Debug
    assert bt["root"] == "Debug"


def test_consumer_conanfile_txt_follows_requested(client):
    """ conanfile.txt consumer settings (used by generators) go through the same patterns """
    client.save({"consumer/conanfile.txt": "[requires]\nmylib/1.0@company/stable\n"})
    client.run("graph info consumer -pr=profile --format=json")
    assert _build_types(client)["root"] == "Debug"  # No name it should always be Debug


def test_consumer_requires_cli_follows_requested(client):
    """ "conan install --requires": the virtual root consumer settings used by generators """
    client.run("graph info --requires=mylib/1.0@company/stable -pr=profile --format=json")
    assert _build_types(client)["root"] == "Debug"  # No name it should always be Debug


class TestCreateAndTestPackage:
    """ "conan create": the package being created and the test_package are both "consumers".
    GenConanfile.with_test() makes the test_package require the tested reference """

    @pytest.fixture()
    def create_client(self, client):
        client.save({"app/conanfile.py": GenConanfile("app", "1.0").with_settings("build_type")
                                         .with_requires("mylib/1.0@company/stable"),
                     "app/test_package/conanfile.py": GenConanfile().with_settings("build_type")
                                                      .with_requires("openssl/1.0")
                                                      .with_test("pass")})
        return client

    def test_create_no_user_channel(self, create_client):
        """ The package being created has a name and no user/channel, so it is a third-party
        package for the "*@" pattern: Release. But the test_package, that has no name, must not
        be affected by it and it follows the requested Debug
        """
        c = create_client
        c.run("create app -pr=profile --build=missing --format=json")
        bt = _build_types(c)
        assert bt["zlib"] == "Release"
        assert bt["openssl"] == "Release"
        assert bt["mylib"] == "Debug"
        assert bt["app"] == "Release"
        # The test_package has no name, it does not match "*@"
        assert bt["root"] == "Debug"

    def test_create_user_channel(self, create_client):
        """ The package being created has user/channel, so it follows the requested Debug, and
        the test_package, that has no name, must follow it too
        """
        c = create_client
        c.run("create app --user=company --channel=stable -pr=profile "
              "--build=missing --format=json")
        bt = _build_types(c)
        assert bt["app"] == "Debug"  # this one follows, it has user/channel
        # The test_package has no name, it does not match "*@"
        assert bt["root"] == "Debug"

    def test_create_user_no_channel(self, create_client):
        """ "pkg/0.1@myuser" (user without channel) is valid, it has user so it is not "*@" and
        it follows Debug, and the unnamed test_package too
        """
        c = create_client
        c.run("create app --user=myuser -pr=profile --build=missing --format=json")
        bt = _build_types(c)
        assert bt["app"] == "Debug"
        # The test_package has no name, it does not match "*@"
        assert bt["root"] == "Debug"

    def test_test_package_checks_tested_build_type(self, client):
        """ A test_package that, as many do, expects to be consistent with the package it
        tests (e.g. CMakeDeps looks for the configuration of its own build_type, and the
        package only exists in Debug). The package has user/channel, so it is Debug, and the
        unnamed test_package must be Debug too
        """
        test = (GenConanfile().with_settings("build_type")
                .with_test("tested = self.dependencies['app'].settings.build_type",
                           "mine = self.settings.build_type",
                           "assert str(tested) == str(mine), f'tested={tested} tp={mine}'"))
        client.save({"app/conanfile.py": GenConanfile("app", "1.0").with_settings("build_type"),
                     "app/test_package/conanfile.py": test})
        client.run("create app --user=company --channel=stable -pr=profile")

    def test_test_package_inconsistent_with_tested_no_user_channel(self, client):
        """ The package being created has no user/channel, so it matches "*@" and it is
        Release, while the unnamed test_package follows the generic Debug. This is a
        consequence of the expected behavior: the tested package and the test_package have
        different build_type, and a test_package expecting consistency fails
        """
        test = (GenConanfile().with_settings("build_type")
                .with_test("tested = self.dependencies['app'].settings.build_type",
                           "mine = self.settings.build_type",
                           "assert str(tested) == str(mine), f'tested={tested} tp={mine}'"))
        client.save({"app/conanfile.py": GenConanfile("app", "1.0").with_settings("build_type"),
                     "app/test_package/conanfile.py": test})
        client.run("create app -pr=profile", assert_error=True)
        assert "tested=Release tp=Debug" in client.out


def test_user_without_channel_dependency(client):
    """ A dependency with user but without channel is not "*@", it follows the requested Debug,
    and the consumer (unnamed) follows it too
    """
    client.save({"userlib/conanfile.py": GenConanfile("userlib", "1.0").with_settings("build_type"),
                 "consumer/conanfile.py": GenConanfile().with_settings("build_type")
                                                        .with_requires("userlib/1.0@myuser",
                                                                       "mylib/1.0@company/stable")})
    client.run("export userlib --user=myuser")
    client.run("graph info consumer -pr=profile --format=json")
    bt = _build_types(client)
    assert bt["zlib"] == "Release"
    assert bt["userlib"] == "Debug"
    assert bt["mylib"] == "Debug"
    # The consumer has no name, it does not match "*@"
    assert bt["root"] == "Debug"
