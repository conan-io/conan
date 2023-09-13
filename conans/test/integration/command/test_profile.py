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


def test_shorthand_syntax():
    tc = TestClient()
    tc.save({"profile": "[conf]\nuser.profile=True"})
    tc.run("profile show -o:a=both_options=True -pr:a=profile -s:a=os=WindowsCE -s:a=os.platform=conan -c:a=user.conf.cli=True")

    # All of them show up twice, once per context
    assert tc.out.count("both_options=True") == 2
    assert tc.out.count("os=WindowsCE") == 2
    assert tc.out.count("os.platform=conan") == 2
    assert tc.out.count("user.conf.cli=True") == 2
    assert tc.out.count("user.profile=True") == 2
