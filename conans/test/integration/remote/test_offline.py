import re

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
    """
    When there are tool-requires that are not installed locally, Conan will try to check
    its existence in the remote, because that package might be needed later. Even if some
    packages can be marked later as "skip" and not fail, that cannot be known a priori, so if the
    package is not in the cache, it will be checked in servers
    https://github.com/conan-io/conan/issues/15339

    Approaches:
    - conan remote disable <remotes>
    - conan install ... -nr (--no-remotes)
    - prepopulate the cache with all tool-requires with `-c:a tools.graph:skip_binaries=False`
    """
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
    assert "ERROR: 'NoneType' object has no attribute 'fake_url'. [Remote: default]" in c.out
    # Explicitly telling that no-remotes, works
    c.run("install --requires=pkg/0.1 -nr")
    assert "Install finished successfully" in c.out

    # graph info also breaks
    c.run("graph info --requires=pkg/0.1", assert_error=True)
    assert "ERROR: 'NoneType' object has no attribute 'fake_url'. [Remote: default]" in c.out

    c.run("graph info --requires=pkg/0.1 -nr")
    assert re.search(r"Skipped binaries(\s*)tool/0.1", c.out)
