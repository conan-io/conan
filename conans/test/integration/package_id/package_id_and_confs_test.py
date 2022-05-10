import textwrap

import pytest

from conans.test.utils.tools import TestClient

PKG_ID_NO_CONF = "cf2e4ff978548fafd099ad838f9ecb8858bf25cb"
PKG_ID_1 = "f0d8262dfb519d89cc56a6d8574e421736f9f6b7"
PKG_ID_2 = "f6d6fc8edeffa6f4c30fbe3510d1375488d0137a"
PKG_ID_3 = "853419ed5bc44fe366b8d09ea1c4bda45d601747"


@pytest.mark.parametrize("package_id_confs, package_id", [
    ('[]', PKG_ID_NO_CONF),
    ('["tools.fake:no_existing_conf"]', PKG_ID_NO_CONF),
    ('["tools.build:cxxflags", "tools.build:cflags"]', PKG_ID_1),
    ('["tools.build:defines"]', PKG_ID_2),
    ('["tools.build:cxxflags", "tools.build:sharedlinkflags"]', PKG_ID_3),
])
def test_package_id_including_confs(package_id_confs, package_id):
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            settings = "os"
        """)
    profile = textwrap.dedent(f"""
    include(default)
    [conf]
    tools.info.package_id:confs={package_id_confs}
    tools.build:cxxflags=["--flag1", "--flag2"]
    tools.build:cflags+=["--flag3", "--flag4"]
    tools.build:sharedlinkflags=+["--flag5", "--flag6"]
    tools.build:exelinkflags=["--flag7", "--flag8"]
    tools.build:defines=["D1", "D2"]
    """)
    client.save({"conanfile.py": conanfile, "profile": profile})
    client.run('create . --name=pkg --version=0.1 -s os=Windows -pr profile')
    client.assert_listed_binary({"pkg/0.1": (package_id, "Build")})


PKG_ID_4 = "9a11cde1f104602e41b217a5f777f441de73a9f2"
PKG_ID_5 = "ea3b400a04f1c479b6817e49b745ca7cf10a9f67"


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
