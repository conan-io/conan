import textwrap

import pytest

from conan.test.utils.tools import GenConanfile, TestClient, NO_SETTINGS_PACKAGE_ID

PKG_ID_NO_CONF = "ebec3dc6d7f6b907b3ada0c3d3cdc83613a2b715"
PKG_ID_1 = "89d32f25195a77f4ae2e77414b870781853bdbc1"
PKG_ID_2 = "7f9ed92704709f56ecc7b133322479caf3ffd7ad"
PKG_ID_3 = "a9f917f3bad3b48b5bceae70214764274ccd6337"
PKG_ID_USER_1 = "571b5dae13b37a78c1993842739bd475879092ea"
PKG_ID_USER_2 = "54a394d26f9c35add86f20ac02cacc3c7e18f02c"
PKG_ID_USER_3 = "54a394d26f9c35add86f20ac02cacc3c7e18f02c"


@pytest.mark.parametrize("package_id_confs, package_id", [
    ('[]', PKG_ID_NO_CONF),
    ('["user.fake:no_existing_conf"]', PKG_ID_NO_CONF),
    ('["tools.build:cxxflags", "tools.build:cflags"]', PKG_ID_1),
    ('["tools.build:defines"]', PKG_ID_2),
    ('["tools.build:cxxflags", "tools.build:sharedlinkflags"]', PKG_ID_3),
    ('["user.foo:value"]', PKG_ID_USER_1),
    ('["user.foo:value", "user.bar:value"]', PKG_ID_USER_2),
    ('["user.*"]', PKG_ID_USER_3),
])
def test_package_id_including_confs(package_id_confs, package_id):
    client = TestClient()
    profile = textwrap.dedent(f"""
    include(default)
    [conf]
    tools.info.package_id:confs={package_id_confs}
    tools.build:cxxflags=["--flag1", "--flag2"]
    tools.build:cflags+=["--flag3", "--flag4"]
    tools.build:sharedlinkflags=+["--flag5", "--flag6"]
    tools.build:exelinkflags=["--flag7", "--flag8"]
    tools.build:defines=["D1", "D2"]

    user.foo:value=1
    user.bar:value=2
    """)
    client.save({"conanfile.py": GenConanfile("pkg", "0.1").with_settings("os"),
                 "profile": profile})
    client.run('create . -s os=Windows -pr profile')
    client.assert_listed_binary({"pkg/0.1": (package_id, "Build")})


PKG_ID_4 = "9b334fc314f2f2ce26e5280901eabcdd7b3f55a6"
PKG_ID_5 = "5510413d2e6186662cb473fb16ce0a18a3f9e98f"


@pytest.mark.parametrize("cxx_flags, package_id", [
    ('[]', PKG_ID_NO_CONF),
    ('["--flag1", "--flag2"]', PKG_ID_4),
    ('["--flag3", "--flag4"]', PKG_ID_5),
])
def test_same_package_id_configurations_but_changing_values(cxx_flags, package_id):
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            settings = "os"
        """)
    profile = textwrap.dedent(f"""
    include(default)
    [conf]
    tools.info.package_id:confs=["tools.build:cxxflags"]
    tools.build:cxxflags={cxx_flags}
    tools.build:cflags+=["--flag3", "--flag4"]
    tools.build:sharedlinkflags=+["--flag5", "--flag6"]
    tools.build:exelinkflags=["--flag7", "--flag8"]
    tools.build:defines=["D1", "D2"]
    """)
    client.save({"conanfile.py": conanfile, "profile": profile})
    client.run('create . --name=pkg --version=0.1 -s os=Windows -pr profile')
    client.assert_listed_binary({"pkg/0.1": (package_id, "Build")})


def test_package_id_confs_header_only():
    """
    The tools.info.package_id:confs cannot affect header-only libraries
    and any other library that does ``self.info.clear()`` in ``package_id()`` method
    """
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            package_type = "header-library"
            implements = ["auto_header_only"]
        """)
    profile = textwrap.dedent(f"""
        include(default)
        [conf]
        tools.info.package_id:confs=["tools.build:cxxflags"]
        """)
    client.save({"conanfile.py": conanfile, "profile": profile})
    client.run('create . --name=pkg --version=0.1 -pr profile -c tools.build:cxxflags=["--flag1"]')
    client.assert_listed_binary({"pkg/0.1": (NO_SETTINGS_PACKAGE_ID, "Build")})
    client.run("list *:*")
    assert "tools.build:cxxflags" not in client.out
    client.run('create . --name=pkg --version=0.1 -pr profile -c tools.build:cxxflags=["--flag2"]')
    client.assert_listed_binary({"pkg/0.1": (NO_SETTINGS_PACKAGE_ID, "Build")})
    client.run("list *:*")
    assert "tools.build:cxxflags" not in client.out


def test_conf_pkg_id_user_pattern_not_defined():
    tc = TestClient(light=True)
    tc.save({"lib/conanfile.py": GenConanfile("lib", "1.0")})
    tc.save_home({"global.conf": "tools.info.package_id:confs=['user.*']"})

    # This used to break the build because `user.*` conf was not valid
    tc.run("create lib")
    assert "lib/1.0: Package 'da39a3ee5e6b4b0d3255bfef95601890afd80709' created" in tc.out


@pytest.mark.parametrize("conf,pkgconf", [
    ("user.foo:value=1\nuser.bar:value=2", "['user.foo:value', 'user.bar:value']"),
    ("user.foo:value=1\nuser.bar:value=2", "['user.bar:value', 'user.foo:value']"),
    ("user.bar:value=2\nuser.foo:value=1", "['user.foo:value', 'user.bar:value']"),
    ("user.bar:value=2\nuser.foo:value=1", "['user.bar:value', 'user.foo:value']"),
])
def test_package_id_order(conf, pkgconf):
    """Ensure the order of the definitions in the conf file does not affect the package_id"""
    tc = TestClient(light=True)
    tc.save({"profile": f"[conf]\ntools.info.package_id:confs={pkgconf}\n" +
                        conf,
             "conanfile.py": GenConanfile("pkg", "1.0")})
    tc.run("create . -pr=profile")
    # They should all have the same pkg id - note that this did not happen before 2.0.17
    tc.assert_listed_binary({"pkg/1.0": ("43227c40b8725e89d30a9f97c0652629933a3685", "Build")})
