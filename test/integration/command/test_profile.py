import json
import os
import textwrap

from conan.test.utils.tools import TestClient


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
    tc.save({"profile": "[conf]\nuser:profile=True"})
    tc.run("profile show -h")
    assert "[-pr:b" in tc.out
    assert "[-pr:h" in tc.out
    assert "[-pr:a" in tc.out

    tc.run(
        "profile show -o:a=both_options=True -pr:a=profile -s:a=os=WindowsCE -s:a=os.platform=conan -c:a=user.conf:cli=True -f=json")

    out = json.loads(tc.stdout)
    assert out == {'build': {'build_env': '',
                             'conf': {'user.conf:cli': True, 'user:profile': True},
                             'options': {'both_options': 'True'},
                             'package_settings': {},
                             'settings': {'os': 'WindowsCE', 'os.platform': 'conan'},
                             'tool_requires': {}},
                   'host': {'build_env': '',
                            'conf': {'user.conf:cli': True, 'user:profile': True},
                            'options': {'both_options': 'True'},
                            'package_settings': {},
                            'settings': {'os': 'WindowsCE', 'os.platform': 'conan'},
                            'tool_requires': {}}}

    tc.save({"pre": textwrap.dedent("""
            [settings]
            os=Linux
            compiler=gcc
            compiler.version=11
            """),
             "mid": textwrap.dedent("""
            [settings]
            compiler=clang
            compiler.version=14
            """),
             "post": textwrap.dedent("""
            [settings]
            compiler.version=13
            """)})

    tc.run("profile show -pr:a=pre -pr:a=mid -pr:a=post -f=json")
    out = json.loads(tc.stdout)
    assert out == {'build': {'build_env': '',
                             'conf': {},
                             'options': {},
                             'package_settings': {},
                             'settings': {'compiler': 'clang',
                                          'compiler.version': '13',
                                          'os': 'Linux'},
                             'tool_requires': {}},
                   'host': {'build_env': '',
                            'conf': {},
                            'options': {},
                            'package_settings': {},
                            'settings': {'compiler': 'clang',
                                         'compiler.version': '13',
                                         'os': 'Linux'},
                            'tool_requires': {}}}

    tc.run("profile show -pr:a=pre -pr:h=post -f=json")
    out = json.loads(tc.stdout)
    assert out == {'build': {'build_env': '',
                             'conf': {},
                             'options': {},
                             'package_settings': {},
                             'settings': {'compiler': 'gcc',
                                          'compiler.version': '11',
                                          'os': 'Linux'},
                             'tool_requires': {}},
                   'host': {'build_env': '',
                            'conf': {},
                            'options': {},
                            'package_settings': {},
                            'settings': {'compiler': 'gcc',
                                         'compiler.version': '13',
                                         'os': 'Linux'},
                            'tool_requires': {}}}

    tc.run("profile show -pr:a=pre -o:b foo=False -o:a foo=True -o:h foo=False -f=json")
    out = json.loads(tc.stdout)
    assert out == {'build': {'build_env': '',
                             'conf': {},
                             'options': {'foo': 'True'},
                             'package_settings': {},
                             'settings': {'compiler': 'gcc',
                                          'compiler.version': '11',
                                          'os': 'Linux'},
                             'tool_requires': {}},
                   'host': {'build_env': '',
                            'conf': {},
                            'options': {'foo': 'False'},
                            'package_settings': {},
                            'settings': {'compiler': 'gcc',
                                         'compiler.version': '11',
                                         'os': 'Linux'},
                            'tool_requires': {}}}


def test_profile_show_json():
    c = TestClient()
    c.save({"myprofilewin": "[settings]\nos=Windows\n"
                            "[tool_requires]\nmytool/*:mytool/1.0\n"
                            "[conf]\nuser.conf:value=42\nlibiconv/*:tools.env.virtualenv:powershell=False\n"
                            "[options]\n*:myoption=True\n"
                            "[replace_requires]\ncmake/*: cmake/3.29.0\n"
                            "[platform_requires]\ncmake/3.29.0\n",
            "myprofilelinux": "[settings]\nos=Linux"})
    c.run("profile show -pr:b=myprofilewin -pr:h=myprofilelinux --format=json")

    profile = json.loads(c.stdout)
    assert profile["host"]["settings"] == {"os": "Linux"}

    assert profile["build"]["settings"] == {"os": "Windows"}
    # Check that tool_requires are properly serialized in json format
    # https://github.com/conan-io/conan/issues/15183
    assert profile["build"]["tool_requires"] == {'mytool/*': ["mytool/1.0"]}
