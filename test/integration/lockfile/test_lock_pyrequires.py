import json
import os
import textwrap

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient
from conan.internal.util.files import load


def test_transitive_py_requires():
    # https://github.com/conan-io/conan/issues/5529
    client = TestClient(light=True)
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
    client = TestClient(light=True)
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


def test_lock_pyrequires_prereleases():
    tc = TestClient(light=True)
    tc.save({"dep/conanfile.py": GenConanfile("dep", "1.0-0.1"),
             "app/conanfile.py": GenConanfile("app", "1.0").with_python_requires("dep/[>=0]")})
    tc.run("export dep")
    dep_rrev = tc.exported_recipe_revision()
    tc.run("lock create app --lockfile-out=app.lock", assert_error=True)
    # Makes sense, prereleases are not active
    assert ("Version range '>=0' from requirement 'dep/[>=0]' required by "
            "'python_requires' could not be resolved") in tc.out

    tc.save_home({"global.conf": "core.version_ranges:resolve_prereleases=True"})
    # This used to crash even with the conf activated
    tc.run("lock create app --lockfile-out=app.lock")
    data = json.loads(load(os.path.join(tc.current_folder, "app.lock")))
    assert data["python_requires"][0].startswith(f"dep/1.0-0.1#{dep_rrev}")


def test_lock_pyrequires_create():
    c = TestClient(light=True)
    c.save({"conanfile.py": GenConanfile("tool", "0.1").with_package_type("python-require")})
    c.run("create .  --lockfile-out=conan.lock")
    lock = json.loads(c.load("conan.lock"))
    assert "tool/0.1#7835890f1e86b3f7fc6d76b4e3c43cb1" in lock["python_requires"][0]


def test_lock_pyrequires_export():
    c = TestClient(light=True)
    c.save({"conanfile.py": GenConanfile("tool", "0.1").with_package_type("python-require")})
    c.run("export .  --lockfile-out=conan.lock")
    lock = json.loads(c.load("conan.lock"))
    assert "tool/0.1#7835890f1e86b3f7fc6d76b4e3c43cb1" in lock["python_requires"][0]


def test_lock_pyrequires_export_transitive():
    c = TestClient(light=True)
    c.save({"dep/conanfile.py": GenConanfile("dep", "0.1").with_package_type("python-require"),
            "tool/conanfile.py": GenConanfile("tool", "0.1").with_package_type("python-require")
                                                            .with_python_requires("dep/0.1")})
    c.run("export dep")
    c.run("export tool --lockfile-out=conan.lock")
    lock = json.loads(c.load("conan.lock"))
    assert "tool/0.1#c0008d3fcf07f7a690dd16bf6c171cec" in lock["python_requires"][0]
    assert "dep/0.1#5d31586a2a4355d68898875dc591009a" in lock["python_requires"][1]


def test_lock_export_transitive_pyrequire():
    # https://github.com/conan-io/conan/issues/19340 was producing errors, it seems
    # that exclusively the exported ref should be added to the lockfile, or if it is a
    # python require, then the transitive python-requires, but not the python-requires of a
    # regular package
    c = TestClient(light=True)
    c.save({"dep/conanfile.py": GenConanfile("dep", "0.1").with_package_type("python-require"),
            "pkg/conanfile.py": GenConanfile("pkg", "0.1").with_python_requires("dep/0.1")})
    c.run("export dep")
    c.run("export pkg --lockfile-out=conan.lock")
    lock = json.loads(c.load("conan.lock"))
    assert "pkg/0.1#dfd6bc1becb3915043a671111860baee" in lock["requires"][0]
    assert lock["python_requires"] == []

    # but if we create
    c.run("create pkg --lockfile-out=conan.lock")
    lock = json.loads(c.load("conan.lock"))
    assert "dep/0.1#5d31586a2a4355d68898875dc591009a" in lock["python_requires"][0]


def test_pyrequires_test_package_lockfile_error():
    # https://github.com/conan-io/conan/issues/19340
    c = TestClient(light=True)
    bar = textwrap.dedent("""
        from conan import ConanFile
        class Bar(ConanFile):
            name = "bar"
            version = "8.0.0"
            python_requires = "conan-utils/[^1]"
     """)
    test_bar = textwrap.dedent("""
        from conan import ConanFile
        class TestBar(ConanFile):
            python_requires = "conan-utils/[^1]"
            def requirements(self):
                self.requires(self.tested_reference_str)
            def test(self):
                pass
        """)
    foo = textwrap.dedent("""
        from conan import ConanFile
        class Foo(ConanFile):
            name = "foo"
            version = "1.0"
            python_requires = "conan-utils/1.7.1"
            requires = "bar/[^8]"
         """)

    c.save({"utils/conanfile.py": GenConanfile("conan-utils").with_package_type("python-require"),
            "bar/conanfile.py": bar,
            "bar/test_package/conanfile.py": test_bar,
            "foo/conanfile.py": foo})

    c.run("create utils --version=1.7.1")
    c.run("create utils --version=1.8.0")
    c.run("create bar")
    c.run("create foo --lockfile-out=conan.lock")
    c.assert_listed_require({"conan-utils/1.7.1": "Cache",
                             "conan-utils/1.8.0": "Cache"}, python=True)
    assert "conan-utils/[^1]: conan-utils/1.8.0" in c.out
    # It works, no longer fails
    lock = json.loads(c.load("conan.lock"))
    assert "conan-utils/1.8.0" in lock["python_requires"][0]
    assert "conan-utils/1.7.1" in lock["python_requires"][1]


def test_pyrequires_test_package_lockfile_error_forward():
    # https://github.com/conan-io/conan/issues/19340
    c = TestClient(light=True)
    bar = textwrap.dedent("""
        from conan import ConanFile
        class Bar(ConanFile):
            name = "bar"
            version = "8.0.0"
            python_requires = "conan-utils/[^1]"
     """)
    test_bar = textwrap.dedent("""
        from conan import ConanFile
        class TestBar(ConanFile):
            python_requires = "conan-utils/[^1]"
            def requirements(self):
                self.requires(self.tested_reference_str)
            def test(self):
                pass
        """)
    foo = textwrap.dedent("""
        from conan import ConanFile
        class Foo(ConanFile):
            name = "foo"
            version = "1.0"
            python_requires = "conan-utils/1.9.0"
            requires = "bar/[^8]"
         """)

    c.save({"utils/conanfile.py": GenConanfile("conan-utils").with_package_type("python-require"),
            "bar/conanfile.py": bar,
            "bar/test_package/conanfile.py": test_bar,
            "foo/conanfile.py": foo})

    c.run("create utils --version=1.8.0")
    c.run("create bar --lockfile-out=conan.lock")
    print(c.load("conan.lock"))
    c.run("create utils --version=1.9.0")
    c.run("create foo --lockfile=conan.lock --lockfile-out=conan.lock")

    c.assert_listed_require({"conan-utils/1.7.1": "Cache",
                             "conan-utils/1.8.0": "Cache"}, python=True)
    assert "conan-utils/[^1]: conan-utils/1.8.0" in c.out
    # It works, no longer fails
    lock = json.loads(c.load("conan.lock"))
    assert "conan-utils/1.8.0" in lock["python_requires"][0]
    assert "conan-utils/1.7.1" in lock["python_requires"][1]
