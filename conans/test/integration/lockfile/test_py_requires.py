import textwrap

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_transitive_py_requires():
    # https://github.com/conan-io/conan/issues/5529
    creator = TestClient()
    client = TestClient(cache_folder=creator.cache_folder)
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        class PackageInfo(ConanFile):
            python_requires = "dep/[>0.0]@user/channel"
        """)
    creator.save({"dep/conanfile.py": GenConanfile(),
                  "pkg/conanfile.py": conanfile})
    creator.run("export dep dep/0.1@user/channel")
    creator.run("export pkg pkg/0.1@user/channel")

    conanfile = textwrap.dedent("""
        from conans import ConanFile
        class MyConanfileBase(ConanFile):
            python_requires = "pkg/0.1@user/channel"
        """)
    client.save({"conanfile.py": conanfile})
    client.run("lock create conanfile.py --lockfile-out=conan.lock")

    creator.run("export dep dep/0.2@user/channel")

    client.run("install conanfile.py --lockfile=conan.lock")
    assert "dep/0.1@user/channel" in client.out
    assert "dep/0.2" not in client.out

    client.run("install conanfile.py")
    assert "dep/0.2@user/channel" in client.out
    assert "dep/0.1" not in client.out
