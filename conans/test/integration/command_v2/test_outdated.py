import textwrap

from assets.genconanfile import GenConanfile
from utils.tools import TestClient


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
    tc.run("graph outdated .")

    print()

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

    tc.run("graph outdated .")
    # assert que el wanted de foo es 2.0

    tc.run("lock create .")
    tc.run("graph outdated .")
    # assert que el wanted de foo es 1.0

    tc.run("lock add --requires=foo/2.0")
    tc.run("graph outdated .")
    # assert que el wanted de foo es 2.0


    # tc.run("graph info . --update")
    tc.run("graph outdated .")

    print()

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
    tc.run("graph outdated .")

    print()

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
    # tc.run("graph info . --update")
    tc.run("graph outdated .")

    print()
