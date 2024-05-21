# coding=utf-8

import textwrap

import pytest

from conan.test.utils.tools import TestClient


@pytest.mark.artifactory_ready
def test_conaninfo_special_chars():

    t = TestClient(default_server_user=True)
    conanfile = textwrap.dedent("""
    # coding=utf-8
    from conan import ConanFile

    class Recipe(ConanFile):
        name = "weird_info"
        version = "1.0"
        options = {"ññ¨¨&是": ['是"是', '][{}"是是是']}
        default_options = {"ññ¨¨&是": '][{}"是是是'}
    """)

    t.save({"conanfile.py": conanfile})
    t.run("create . ")
    t.run('list weird_info/1.0:*')
    assert 'ññ¨¨&是: ][{}"是是是' in t.out

    t.run("upload * -c -r default")
    # TODO: I have struggled with this, it was not accepting "latest", revision needs explicit one
    t.run('list weird_info/1.0#8c9e59246220eef8ca3bd4ac4f39ceb3:* -r default')
    assert 'ññ¨¨&是: ][{}"是是是' in t.out
