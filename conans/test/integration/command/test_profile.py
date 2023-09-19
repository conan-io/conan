import json
import os
import textwrap

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
    tc.run("profile show -h")
    assert "[-pr:b" in tc.out
    assert "[-pr:h" in tc.out
    assert "[-pr:a" in tc.out

    tc.run("profile show -o:a=both_options=True -pr:a=profile -s:a=os=WindowsCE -s:a=os.platform=conan -c:a=user.conf.cli=True")

    # All of them show up twice, once per context
    assert tc.out.count("both_options=True") == 2
    assert tc.out.count("os=WindowsCE") == 2
    assert tc.out.count("os.platform=conan") == 2
    assert tc.out.count("user.conf.cli=True") == 2
    assert tc.out.count("user.profile=True") == 2

    tc.save({"pre": textwrap.dedent("""
            [settings]
            os = Linux
            compiler = gcc
            compiler.version = 11
            """),
             "mid": textwrap.dedent("""
            [settings]
            compiler = clang
            compiler.version = 14
            """),
             "post": textwrap.dedent("""
            [settings]
            compiler.version = 13
            """)})
    tc.run("profile show -pr:a=pre -pr:a=mid -pr:a=post")
    assert textwrap.dedent("""
    Host profile:
    [settings]
    compiler=clang
    compiler.version=13
    os=Linux

    Build profile:
    [settings]
    compiler=clang
    compiler.version=13
    os=Linux""") in tc.out


def test_profile_show_json():
    c = TestClient()
    c.save({"myprofilewin": "[settings]\nos=Windows",
            "myprofilelinux": "[settings]\nos=Linux"})
    c.run("profile show -pr:b=myprofilewin -pr:h=myprofilelinux --format=json")
    profile = json.loads(c.stdout)
    assert profile["build"]["settings"] ==  {"os": "Windows"}
    assert profile["host"]["settings"] == {"os": "Linux"}
