import textwrap

from conans.test.utils.tools import TestClient


def test_package_id_include_confs():
    client = TestClient()
    client.save({"global.conf": 'core.package_id:confs=["tools.build:cxxflags", "tools.build:cflags"]'},
                path=client.cache.cache_folder)
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            settings = "os"
        """)
    profile = textwrap.dedent("""
    include(default)
    [conf]
    tools.build:cxxflags=["--flag1", "--flag2"]
    tools.build:cflags+=["--flag3", "--flag4"]
    """)
    client.save({"conanfile.py": conanfile, "profile": profile})
    client.run('create . --name=pkg --version=0.1 -s os=Windows -pr profile')
    # client.assert_listed_binary({"pkg/0.1": ("115c314122246da287f43c08de5eeab316596038",
    #                                          "Build")})
    # client.run('install --requires=pkg/0.1@ -s os=Windows -s compiler=msvc '
    #            '-s compiler.version=190 -s build_type=Debug -s compiler.runtime=dynamic')
    # client.assert_listed_binary({"pkg/0.1": ("115c314122246da287f43c08de5eeab316596038", "Cache")})
