import json
import os

from conans.model.graph_lock import GraphLockFile
from conans.test.utils.tools import TestClient, GenConanfile


def test_regular_package():
    client = TestClient()
    # TODO: This is hardcoded
    client.run("config set general.revisions_enabled=1")
    client.save({"pkga/conanfile.py":     GenConanfile(),
                 "pkgb/conanfile.py":     GenConanfile(),
                 "defaults/conanfile.py": GenConanfile().with_requires("pkga/1.0.0").with_requires("pkgb/1.1.0"), # specify versions in default packages
                 "app/conanfile.py":      GenConanfile().with_requires("pkga/[*]").with_requires("pkgb/[*]")})    # version range in app
             
    # export different version from the libs to the cache         
    client.run("export pkga pkga/1.0.0@")
    client.run("export pkga pkga/1.1.0@")
    client.run("export pkga pkga/1.1.1@")
    client.run("export pkgb pkgb/1.0.0@")
    client.run("export pkgb pkgb/1.1.0@")
    client.run("export pkgb pkgb/1.1.1@")
    client.run("export defaults defaults/1.0@")
    client.run("lock create --reference=defaults/1.0@ --base --lockfile-out=defaults.lock")
    # derive app.lock from defaults.lock
    client.run("lock create app/conanfile.py --lockfile=defaults.lock --lockfile-out=app.lock")
    client.run("install app/conanfile.py --lockfile=app.lock --build=missing")

    # check that specified versions from default package are to be installed for app.
    assert "pkga/1.0.0" in client.out
    assert "pkgb/1.1.0" in client.out


def test_non_semver_package():
    client = TestClient()
    # TODO: This is hardcoded
    client.run("config set general.revisions_enabled=1")
    client.save({"pkga/conanfile.py":     GenConanfile(),
                 "defaults/conanfile.py": GenConanfile().with_requires("pkga/1.0.0i"), #require a non semver version
                 "app/conanfile.py":      GenConanfile().with_requires("pkga/[*]")})
                 
    client.run("export pkga pkga/1.0.0@")
    client.run("export pkga pkga/1.0.0i@")
    client.run("export pkga pkga/1.1.0@")
    client.run("export pkga pkga/1.1.1@")
    client.run("export defaults defaults/1.0@")
    client.run("lock create --reference=defaults/1.0@ --base --lockfile-out=defaults.lock")
    client.run("lock create app/conanfile.py --lockfile=defaults.lock --lockfile-out=app.lock")
    client.run("install app/conanfile.py --lockfile=app.lock --build=missing")

    #assert "pkga/1.0.0i" in client.out

def test_update_package():
    client = TestClient()
    client.save({"pkga/conanfile.py":     GenConanfile(),
                 "pkgb/conanfile.py":     GenConanfile(),
                 # specify versions in default packages
                 "defaults/conanfile.py": GenConanfile().with_requires("pkga/1.0.0",
                                                                                 "pkgb/1.0.0"),
                 # version range in app
                 "app/conanfile.py":      GenConanfile().with_requires("pkga/1.1.0","pkgb/[*]")})

    # export different version from the libs to the cache
    client.run("export pkga pkga/1.0.0@")
    client.run("export pkga pkga/1.1.0@")
    client.run("export pkgb pkgb/1.0.0@")
    client.run("export pkgb pkgb/1.1.0@")
    client.run("export defaults defaults/1.0@")
    client.run("lock create --reference=defaults/1.0@ --base --lockfile-out=defaults.lock")
    # derive app.lock from defaults.lock
    client.run("lock create app/conanfile.py --lockfile=defaults.lock --lockfile-out=app.lock")
    client.run("install app/conanfile.py --lockfile=app.lock --build=missing")

    # check that specified versions from default package are to be installed for app.
    assert "pkga/1.1.0" in client.out
    assert "pkgb/1.0.0" in client.out

def test_update_package_transitive():
    client = TestClient()
    client.save({"pkga/conanfile.py":     GenConanfile(),
                 "pkgb/conanfile.py":     GenConanfile().with_requires("pkga/[*]"),
                 # specify versions in default packages
                 "defaults/conanfile.py": GenConanfile().with_requires("pkga/1.0.0",
                                                                                 "pkgb/1.0.0"),
                 # version range in app
                 "app/conanfile.py":      GenConanfile().with_requires("pkga/1.1.0","pkgb/[*]")})

    # export different version from the libs to the cache
    client.run("export pkga pkga/1.0.0@")
    client.run("export pkga pkga/1.1.0@")
    client.run("export pkgb pkgb/1.0.0@")
    client.run("export pkgb pkgb/1.1.0@")
    client.run("export defaults defaults/1.0@")
    client.run("lock create --reference=defaults/1.0@ --base --lockfile-out=defaults.lock")
    # derive app.lock from defaults.lock
    client.run("lock create app/conanfile.py --lockfile=defaults.lock --lockfile-out=app.lock")
    client.run("install app/conanfile.py --lockfile=app.lock --build=missing")

    # check that specified versions from default package are to be installed for app.
    assert "pkga/1.1.0" in client.out
    assert "pkgb/1.0.0" in client.out