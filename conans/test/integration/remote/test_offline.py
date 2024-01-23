from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_offline():
    c = TestClient(servers={"default": None}, requester_class=None)
    c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
    c.run("create .")
    c.run("install --requires=pkg/0.1")
    # doesn't fail, install without issues
    assert "Install finished successfully" in c.out


def test_offline_uploaded():
    c = TestClient(default_server_user=True)
    c.save({"conanfile.py": GenConanfile("pkg")})
    c.run("create . --version=0.1")
    c.run("create . --version=0.2")
    c.run("upload * -r=default -c")
    c.run("remove * -c")
    c.run("install --requires=pkg/0.1")
    assert "Install finished successfully" in c.out
    c.servers = {"default": None}
    c.run("install --requires=pkg/0.1")
    assert "Install finished successfully" in c.out
    # Lets make sure the server is broken
    c.run("install --requires=pkg/0.2", assert_error=True)
    assert "ERROR: Package 'pkg/0.2' not resolved" in c.out


def test_offline_build_requires():
    c = TestClient(default_server_user=True)
    c.save({"tool/conanfile.py": GenConanfile("tool", "0.1"),
            "lib/conanfile.py": GenConanfile("pkg", "0.1").with_tool_requires("tool/0.1")})
    c.run("create tool")
    c.run("create lib")
    c.run("upload * -r=default -c")
    c.run("remove * -c")
    c.run("install --requires=pkg/0.1")
    assert "Install finished successfully" in c.out
    c.servers = {"default": None}
    c.run("install --requires=pkg/0.1", assert_error=True)
    # At the moment this fails, it doesn't work offline, because the package for the build-require
    # is not locally installed, and Conan will check for it. Later it might decide that it can
    # be skipped, but initially it will look for it, and as it is not in the cache, it will look
    # in the remotes.
    # Explicitly telling that no-remotes, works
    c.run("install --requires=pkg/0.1 -nr")
    assert "Install finished successfully" in c.out
