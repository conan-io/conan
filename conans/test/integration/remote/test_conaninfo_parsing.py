# coding=utf-8

import textwrap

import pytest
import six

from conans.test.utils.tools import TestClient


@pytest.mark.skipif(six.PY2, reason="only Py3")
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
    t.run("upload * -c -r default --all")

    t.run('search weird_info/1.0@ -r default')
    assert 'ññ¨¨&是: ][{}"是是是' in t.out
