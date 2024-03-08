import textwrap

from assets.genconanfile import GenConanfile
from utils.tools import TestClient


def test_invalid_output_level():
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

def test_invalid_output_level_with_lockfile():
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
    conan_lock = textwrap.dedent("""
    {
        "version": "0.5",
        "requires": [
            "zlib/2.0",
            "zlib/1.0#4d670581ccb765839f2239cc8dff8fbd%1709873018.9729314",
            "libcurl/1.0#05ea7551a2e08adf4f01d0061b458db5%1709873019.221777",
            "foo/1.0#4d670581ccb765839f2239cc8dff8fbd%1709873019.09337"
        ],
        "build_requires": [],
        "python_requires": []
    }
    """)
    tc.save({"conan.lock": conan_lock})
    # tc.run("lock create .")
    # tc.run("graph info . --update")
    tc.run("graph outdated .")

    print()
