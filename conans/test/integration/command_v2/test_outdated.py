import json
from collections import OrderedDict

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient, TestServer


def test_outdated_command():
    tc = TestClient(default_server_user=True)
    #Create libraries needed to generate the dependency graph
    tc.save({"conanfile.py": GenConanfile()})
    tc.run("create . --name=zlib --version=1.0")

    tc.run("create . --name=foo --version=1.0")
    tc.save({"conanfile.py": GenConanfile().with_requires("foo/[>=1.0]")})
    tc.run("create . --name=libcurl --version=1.0")

    #Upload the created libraries to remote
    tc.run("upload * -c -r=default")

    #Create new version of libraries in remote and remove them from cache
    tc.save({"conanfile.py": GenConanfile()})
    tc.run("create . --name=foo --version=2.0")
    tc.run("create . --name=zlib --version=2.0")
    tc.run("upload * -c -r=default")
    tc.run("remove foo/2.0 -c")
    tc.run("remove zlib/2.0 -c")

    tc.save({"conanfile.py": GenConanfile("app", "1.0").with_requires("zlib/1.0", "libcurl/[>=1.0]")})
    # tc.run("graph info . --update")
    tc.run("graph outdated . --format=json")
    output = json.loads(tc.stdout)
    assert "zlib" in output
    assert "foo" in output
    assert "libcurl" not in output
    assert output["zlib"]["current"].startswith("zlib/1.0")
    assert output["zlib"]["latest_range"].startswith("zlib/1.0")
    assert output["zlib"]["latest_remote"]["ref"].startswith("zlib/2.0")
    assert output["zlib"]["latest_remote"]["remote"].startswith("default")
    assert output["foo"]["current"].startswith("foo/1.0")
    assert output["foo"]["latest_range"].startswith("foo/2.0")
    assert output["foo"]["latest_remote"]["ref"].startswith("foo/2.0")
    assert output["foo"]["latest_remote"]["remote"].startswith("default")


def test_recipe_with_lockfile():
    tc = TestClient(default_server_user=True)
    # Create libraries needed to generate the dependency graph
    tc.save({"conanfile.py": GenConanfile()})
    tc.run("create . --name=zlib --version=1.0")
    tc.run("create . --name=foo --version=1.0")

    tc.save({"conanfile.py": GenConanfile().with_requires("foo/[>=1.0]")})
    tc.run("create . --name=libcurl --version=1.0")

    # Upload the created libraries to remote
    tc.run("upload * -c -r=default")

    # Create new version of libraries in remote and remove them from cache
    tc.save({"conanfile.py": GenConanfile()})
    tc.run("create . --name=foo --version=2.0")
    tc.run("create . --name=zlib --version=2.0")
    tc.run("upload * -c -r=default")
    tc.run("remove foo/2.0 -c")
    tc.run("remove zlib/2.0 -c")

    tc.save({"conanfile.py": GenConanfile("app", "1.0").with_requires("zlib/1.0",
                                                                      "libcurl/[>=1.0]")})

    tc.run("graph outdated . --format=json")
    output = json.loads(tc.stdout)
    assert "zlib" in output
    assert "foo" in output
    assert "libcurl" not in output
    assert output["foo"]["latest_range"].startswith("foo/2.0")

    # Creating the lockfile sets foo/1.0 as only valid version for the recipe
    tc.run("lock create .")
    tc.run("graph outdated . --format=json")
    output = json.loads(tc.stdout)
    assert output["foo"]["latest_range"].startswith("foo/1.0")

    # Adding foo/2.0 to the lockfile forces the download so foo is no longer outdated
    tc.run("lock add --requires=foo/2.0")
    tc.run("graph outdated . --format=json")
    output = json.loads(tc.stdout)
    assert "foo" not in output


def test_recipe_with_no_remote_ref():
    tc = TestClient(default_server_user=True)
    # Create libraries needed to generate the dependency graph
    tc.save({"conanfile.py": GenConanfile()})
    tc.run("create . --name=zlib --version=1.0")
    tc.run("create . --name=foo --version=1.0")

    tc.save({"conanfile.py": GenConanfile().with_requires("foo/[>=1.0]")})
    tc.run("upload * -c -r=default")

    #libcurl recipe only exists in local
    tc.run("create . --name=libcurl --version=1.0")

    # Create new version of libraries in remote and remove them from cache
    tc.save({"conanfile.py": GenConanfile()})
    tc.run("create . --name=foo --version=2.0")
    tc.run("create . --name=zlib --version=2.0")
    tc.run("upload foo/* -c -r=default")
    tc.run("upload zlib/* -c -r=default")
    tc.run("remove foo/2.0 -c")
    tc.run("remove zlib/2.0 -c")

    tc.save({"conanfile.py": GenConanfile("app", "1.0").with_requires("zlib/1.0",
                                                                      "libcurl/[>=1.0]")})
    # tc.run("graph info . --update")
    tc.run("graph outdated . --format=json")
    output = json.loads(tc.stdout)
    assert "zlib" in output
    assert "foo" in output
    assert "libcurl" not in output


def test_cache_ref_newer_than_latest_in_remote():
    tc = TestClient(default_server_user=True)
    # Create libraries needed to generate the dependency graph
    tc.save({"conanfile.py": GenConanfile()})
    tc.run("create . --name=zlib --version=1.0")
    tc.run("create . --name=foo --version=1.0")

    tc.save({"conanfile.py": GenConanfile().with_requires("foo/[>=1.0]")})
    tc.run("create . --name=libcurl --version=1.0")

    # Upload the created libraries to remote
    tc.run("upload * -c -r=default")

    # Create new version of libraries in remote and remove them from cache
    tc.save({"conanfile.py": GenConanfile()})
    tc.run("create . --name=zlib --version=2.0")
    tc.run("upload * -c -r=default")
    tc.run("create . --name=foo --version=2.0")

    tc.save({"conanfile.py": GenConanfile("app", "1.0").with_requires("zlib/1.0",
                                                                      "libcurl/[>=1.0]")})

    tc.run("list foo")
    tc.run("list foo -r default")

    tc.run("graph outdated . --format=json")
    output = json.loads(tc.stdout)
    assert "zlib" in output
    assert "libcurl" not in output
    assert "foo" not in output


def test_two_remotes():
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

    tc.save({"conanfile.py": GenConanfile("app", "1.0").with_requires("zlib/1.0",
                                                                      "libcurl/[>=1.0]")})

    tc.run("graph outdated . --format=json")
    output = json.loads(tc.stdout)
    assert "zlib" in output
    assert "libcurl" in output
    assert "foo" not in output
    assert output["libcurl"]["latest_remote"]["ref"].startswith("libcurl/2.0")
    assert output["libcurl"]["latest_remote"]["remote"].startswith("remote1")
    assert output["zlib"]["latest_remote"]["ref"].startswith("zlib/2.0")
    assert output["zlib"]["latest_remote"]["remote"].startswith("remote2")
    #test donde version del remoto esta por encima de un rango


def test_multiple_call_to_single_reference():
    tc = TestClient(default_server_user=True)
    # Create libraries needed to generate the dependency graph
    tc.save({"conanfile.py": GenConanfile()})
    tc.run("create . --name=cmake --version=1.0")
    tc.run("create . --name=cmake --version=2.0")
    tc.run("create . --name=cmake --version=3.0")
    tc.save({"conanfile.py": GenConanfile().with_tool_requires("cmake/1.0")})
    tc.run("create . --name=foo --version=1.0")
    tc.save({"conanfile.py": GenConanfile().with_tool_requires("cmake/2.0")})
    tc.run("create . --name=bar --version=1.0")

    # Upload the created libraries to remote
    tc.run("upload * -c -r=default")

    tc.run("remove cmake/2.0 -c")
    tc.run("remove cmake/3.0 -c")

    tc.save(
        {"conanfile.py": GenConanfile("app", "1.0").with_requires("foo/1.0", "bar/1.0", "cmake/[>=1.0]")})
    # tc.run("graph info . --update")
    tc.run("graph outdated . --format=json")
    print()
