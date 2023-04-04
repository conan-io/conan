import os

from conans.test.utils.tools import TestClient


def test_profile_path():
    c = TestClient()
    c.run("profile path default")
    assert "default" in c.out


def test_profile_path_missing():
    c = TestClient()
    c.run("profile path notexisting", assert_error=True)
    assert "ERROR: Profile not found: notexisting" in c.out


def test_ignore_paths_when_listing_profiles():
    c = TestClient()
    ignore_path = '.DS_Store'

    # just in case
    os.makedirs(c.cache.profiles_path, exist_ok=True)
    # This a "touch" equivalent
    open(os.path.join(c.cache.profiles_path, '.DS_Store'), 'w').close()
    os.utime(os.path.join(c.cache.profiles_path, ".DS_Store"))

    c.run("profile list")

    assert ignore_path not in c.out


def test_conf_global_cli():
    tc = TestClient()

    tc.run("profile show -c user.myconf:key=value -gc core.download:retry=10")

    assert "core.download:retry=10" in tc.out
    assert tc.out.count("core.download:retry=10") == 2
    assert "user.myconf:key=value" in tc.out
    assert tc.out.count("user.myconf:key=value") == 1


def test_conf_global_cli_rebase():
    tc = TestClient()

    # Ensure -c wins over -gc
    tc.run("profile show -c tools.build:jobs=9 -gc tools.build:jobs=42")
    assert "tools.build:jobs=9" in tc.out
    assert "tools.build:jobs=42" in tc.out

    # Also ensure -c:b & -c:h wins over -gc just in case
    tc.run("profile show -c:b tools.build:jobs=9 -c:h tools.build:jobs=17 -gc tools.build:jobs=42")
    assert "tools.build:jobs=9" in tc.out
    assert "tools.build:jobs=17" in tc.out
    assert "tools.build:jobs=42" not in tc.out


def test_conf_global_cli_file():
    # Ensure CLI has priority over global.conf
    tc = TestClient()
    tc.save_home({"global.conf": "core.download:retry=9"})

    tc.run("profile show -gc core.download:retry=13")
    assert "core.download:retry=13" in tc.out
    assert "core.download:retry=9" not in tc.out
