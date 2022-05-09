import os
import textwrap

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_transitive_py_requires():
    # https://github.com/conan-io/conan/issues/5529
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class PackageInfo(ConanFile):
            python_requires = "dep/[>0.0]@user/channel"
        """)
    consumer = textwrap.dedent("""
        from conan import ConanFile
        class MyConanfileBase(ConanFile):
            python_requires = "pkg/0.1@user/channel"
        """)
    client.save({"dep/conanfile.py": GenConanfile(),
                 "pkg/conanfile.py": conanfile,
                 "consumer/conanfile.py": consumer})

    client.run("export dep --name=dep --version=0.1 --user=user --channel=channel")
    client.run("export pkg --name=pkg --version=0.1 --user=user --channel=channel")
    client.run("lock create consumer/conanfile.py")

    client.run("export dep --name=dep --version=0.2 --user=user --channel=channel")

    client.run("install consumer/conanfile.py")
    assert "dep/0.1@user/channel" in client.out
    assert "dep/0.2" not in client.out

    os.remove(os.path.join(client.current_folder, "consumer/conan.lock"))
    client.run("install consumer/conanfile.py")
    assert "dep/0.2@user/channel" in client.out
    assert "dep/0.1" not in client.out


def test_transitive_matching_ranges():
    client = TestClient()
    tool = textwrap.dedent("""
        from conan import ConanFile
        class PackageInfo(ConanFile):
            python_requires = "dep/{}"
        """)
    pkg = textwrap.dedent("""
        from conan import ConanFile
        class MyConanfileBase(ConanFile):
            python_requires = "tool/{}"
            def configure(self):
                for k, p in self.python_requires.items():
                    self.output.info("%s: %s!!" % (k, p.ref))
        """)
    client.save({"dep/conanfile.py": GenConanfile(),
                 "tool1/conanfile.py": tool.format("[<0.2]"),
                 "tool2/conanfile.py": tool.format("[>0.0]"),
                 "pkga/conanfile.py": pkg.format("[<0.2]"),
                 "pkgb/conanfile.py": pkg.format("[>0.0]"),
                 "app/conanfile.py": GenConanfile().with_requires("pkga/[*]", "pkgb/[*]")})

    client.run("export dep --name=dep --version=0.1")
    client.run("export dep --name=dep --version=0.2")
    client.run("export tool1 --name=tool --version=0.1")
    client.run("export tool2 --name=tool --version=0.2")
    client.run("create pkga --name=pkga --version=0.1")
    client.run("create pkgb --name=pkgb --version=0.1")
    client.run("lock create app/conanfile.py --lockfile-out=app.lock")

    client.run("export dep --name=dep --version=0.2")
    client.run("export tool2 --name=tool --version=0.3")
    client.run("create pkga --name=pkga --version=0.2")
    client.run("create pkgb --name=pkgb --version=0.2")

    client.run("install app/conanfile.py --lockfile=app.lock")
    assert "pkga/0.1: tool: tool/0.1!!" in client.out
    assert "pkga/0.1: dep: dep/0.1!!" in client.out
    assert "pkgb/0.1: tool: tool/0.2!!" in client.out
    assert "pkgb/0.1: dep: dep/0.2!!" in client.out

    client.run("install app/conanfile.py")
    assert "pkga/0.2: tool: tool/0.1!!" in client.out
    assert "pkga/0.2: dep: dep/0.1!!" in client.out
    assert "pkgb/0.2: tool: tool/0.3!!" in client.out
    assert "pkgb/0.2: dep: dep/0.2!!" in client.out
