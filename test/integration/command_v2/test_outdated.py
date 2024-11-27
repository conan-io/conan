import json
from collections import OrderedDict

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient, TestServer


@pytest.fixture
def create_libs():
    tc = TestClient(default_server_user=True)
    tc.save({"conanfile.py": GenConanfile()})
    tc.run("create . --name=zlib --version=1.0")
    tc.run("create . --name=zlib --version=2.0")
    tc.run("create . --name=foo --version=1.0")
    tc.run("create . --name=foo --version=2.0")

    tc.save({"conanfile.py": GenConanfile().with_requires("foo/[>=1.0]")})
    tc.run("create . --name=libcurl --version=1.0")

    # Upload all created libs to the remote
    tc.run("upload * -c -r=default")

    tc.save({"conanfile.py": GenConanfile("app", "1.0")
            .with_requires("zlib/1.0", "libcurl/[>=1.0]")})
    return tc


def test_outdated_command(create_libs):
    tc = create_libs

    # Remove versions from cache so they are found as outdated
    tc.run("remove foo/2.0 -c")
    tc.run("remove zlib/2.0 -c")

    tc.run("graph outdated . --format=json")
    output = json.loads(tc.stdout)
    assert "zlib" in output
    assert "foo" in output
    assert "libcurl" not in output
    assert output["zlib"]["current_versions"] == ["zlib/1.0"]
    assert output["zlib"]["version_ranges"] == []
    assert output["zlib"]["latest_remote"]["ref"] == "zlib/2.0"
    assert output["zlib"]["latest_remote"]["remote"].startswith("default")
    assert output["foo"]["current_versions"] == ["foo/1.0"]
    assert output["foo"]["version_ranges"] == ["foo/[>=1.0]"]
    assert output["foo"]["latest_remote"]["ref"] == "foo/2.0"
    assert output["foo"]["latest_remote"]["remote"].startswith("default")


def test_recipe_with_lockfile(create_libs):
    tc = create_libs

    # Remove versions from cache so they are found as outdated
    tc.run("remove foo/2.0 -c")
    tc.run("remove zlib/2.0 -c")

    # Creating the lockfile sets foo/1.0 as only valid version for the recipe
    tc.run("lock create .")
    tc.run("graph outdated . --format=json")
    output = json.loads(tc.stdout)
    assert "foo" in output
    assert output["foo"]["current_versions"] == ["foo/1.0"]
    # Creating the lockfile makes the previous range obsolete
    assert output["foo"]["version_ranges"] == []

    # Adding foo/2.0 to the lockfile forces the download so foo is no longer outdated
    tc.run("lock add --requires=foo/2.0")
    tc.run("graph outdated . --format=json")
    output = json.loads(tc.stdout)
    assert "foo" not in output


def test_recipe_with_no_remote_ref(create_libs):
    tc = create_libs

    # Remove versions from cache so they are found as outdated
    tc.run("remove foo/2.0 -c")
    tc.run("remove zlib/2.0 -c")
    tc.run("remove libcurl -c")

    tc.run("graph outdated . --format=json")
    output = json.loads(tc.stdout)
    # Check that libcurl doesn't appear as there is no version in the remotes
    assert "zlib" in output
    assert "foo" in output
    assert "libcurl" not in output


def test_cache_ref_newer_than_latest_in_remote(create_libs):
    tc = create_libs

    tc.run("remove foo/2.0 -c -r=default")

    tc.run("graph outdated . --format=json")
    output = json.loads(tc.stdout)
    # Check that foo doesn't appear because the version in cache is higher than the latest version
    # in remote
    assert "zlib" in output
    assert "libcurl" not in output
    assert "foo" not in output


def test_two_remotes():
    # remote1: zlib/1.0, libcurl/2.0, foo/1.0
    # remote2: zlib/[1.0, 2.0], libcurl/1.0, foo/1.0
    # local cache: zlib/1.0, libcurl/1.0, foo/1.0
    servers = OrderedDict()
    for i in [1, 2]:
        test_server = TestServer()
        servers["remote%d" % i] = test_server

    tc = TestClient(servers=servers, inputs=2 * ["admin", "password"], light=True)

    tc.save({"conanfile.py": GenConanfile()})
    tc.run("create . --name=zlib --version=1.0")
    tc.run("create . --name=foo --version=1.0")
    tc.run("create . --name=zlib --version=2.0")

    tc.save({"conanfile.py": GenConanfile().with_requires("foo/[>=1.0]")})
    tc.run("create . --name=libcurl --version=1.0")
    tc.run("create . --name=libcurl --version=2.0")

    # Upload the created libraries  1.0 to remotes
    tc.run("upload zlib/1.0 -c -r=remote1")
    tc.run("upload libcurl/2.0 -c -r=remote1")
    tc.run("upload foo/1.0 -c -r=remote1")

    tc.run("upload zlib/* -c -r=remote2")
    tc.run("upload libcurl/1.0 -c -r=remote2")
    tc.run("upload foo/1.0 -c -r=remote2")

    # Remove from cache the 2.0 libraries
    tc.run("remove libcurl/2.0 -c")
    tc.run("remove zlib/2.0 -c")

    tc.save({"conanfile.py": GenConanfile("app", "1.0")
            .with_requires("zlib/1.0", "libcurl/[>=1.0]")})

    tc.run("graph outdated . --format=json")
    output = json.loads(tc.stdout)
    assert "zlib" in output
    assert "libcurl" in output
    assert "foo" not in output
    assert output["libcurl"]["latest_remote"]["ref"].startswith("libcurl/2.0")
    assert output["libcurl"]["latest_remote"]["remote"].startswith("remote1")
    assert output["zlib"]["latest_remote"]["ref"].startswith("zlib/2.0")
    assert output["zlib"]["latest_remote"]["remote"].startswith("remote2")


def test_duplicated_tool_requires():
    tc = TestClient(default_server_user=True)
    # Create libraries needed to generate the dependency graph
    tc.save({"conanfile.py": GenConanfile()})
    tc.run("create . --name=cmake --version=1.0")
    tc.run("create . --name=cmake --version=2.0")
    tc.run("create . --name=cmake --version=3.0")
    tc.save({"conanfile.py": GenConanfile().with_tool_requires("cmake/1.0")})
    tc.run("create . --name=foo --version=1.0")
    tc.save({"conanfile.py": GenConanfile().with_tool_requires("cmake/[>=1.0]")})
    tc.run("create . --name=bar --version=1.0")

    # Upload the created libraries to remote
    tc.run("upload * -c -r=default")

    tc.save({"conanfile.py": GenConanfile("app", "1.0")
            .with_requires("foo/1.0", "bar/1.0").with_tool_requires("cmake/[<=2.0]")})

    tc.run("graph outdated . --format=json")
    output = json.loads(tc.stdout)

    assert sorted(output["cmake"]["current_versions"]) == ["cmake/1.0", "cmake/2.0", "cmake/3.0"]
    assert sorted(output["cmake"]["version_ranges"]) == ["cmake/[<=2.0]", "cmake/[>=1.0]"]
    assert output["cmake"]["latest_remote"]["ref"] == "cmake/3.0"


def test_no_outdated_dependencies():
    tc = TestClient(default_server_user=True)

    tc.save({"conanfile.py": GenConanfile()})
    tc.run("create . --name=foo --version=1.0")
    tc.run("upload * -c -r=default")

    tc.run("graph outdated .")

    assert "No outdated dependencies in graph" in tc.stdout
