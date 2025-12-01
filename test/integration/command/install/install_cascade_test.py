from collections import OrderedDict

from conan.test.utils.tools import TestServer, GenConanfile, TestClient


def test_cascade():
    """
    app -> E -> D -> B -> A
      \\-> F -> C -------/
    """
    server = TestServer()
    servers = OrderedDict([("default", server)])
    c = TestClient(servers=servers)
    c.save({"a/conanfile.py": GenConanfile("liba", "1.0"),
            "b/conanfile.py": GenConanfile("libb", "1.0").with_requires("liba/1.0"),
            "c/conanfile.py": GenConanfile("libc", "1.0").with_requires("liba/1.0"),
            "d/conanfile.py": GenConanfile("libd", "1.0").with_requires("libb/1.0"),
            "e/conanfile.py": GenConanfile("libe", "1.0").with_requires("libd/1.0"),
            "f/conanfile.py": GenConanfile("libf", "1.0").with_requires("libc/1.0", "libd/1.0"),
            "app/conanfile.py": GenConanfile().with_requires("libe/1.0", "libf/1.0")})

    for pkg in ("a", "b", "c", "d", "e", "f"):
        c.run(f"create {pkg}")

    def _assert_built(refs):
        for ref in refs:
            assert "{}: Copying sources to build folder".format(ref) in c.out
        for ref in ["liba/1.0", "libb/1.0", "libc/1.0", "libd/1.0", "libe/1.0", "libf/1.0"]:
            if ref not in refs:
                assert "{}: Copying sources to build folder".format(ref) not in c.out

    # Building A everything is built
    c.run("install app --build=liba* --build cascade")
    _assert_built(["liba/1.0", "libb/1.0", "libc/1.0", "libd/1.0", "libe/1.0", "libf/1.0"])

    c.run("install app --build=libd* --build cascade")
    _assert_built(["libd/1.0", "libe/1.0", "libf/1.0"])

    c.run("install app --build=libe* --build cascade")
    _assert_built(["libe/1.0"])

    c.run("install app  --build cascade")
    _assert_built([])

    c.run("install app --build=libc* --build cascade")
    _assert_built(["libc/1.0", "libf/1.0"])
