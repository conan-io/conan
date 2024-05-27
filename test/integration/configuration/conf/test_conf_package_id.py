import json
import textwrap

import pytest

from conan.test.utils.tools import TestClient


@pytest.fixture
def client():
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class Pkg(ConanFile):
            def package_id(self):
                self.info.conf.define("user.myconf:myitem", self.conf.get("user.myconf:myitem"))
        """)
    client.save({"conanfile.py": conanfile})
    return client


def test_package_id(client):
    profile1 = textwrap.dedent("""\
        [conf]
        user.myconf:myitem=1""")
    profile2 = textwrap.dedent("""\
        [conf]
        user.myconf:myitem=2""")
    client.save({"profile1": profile1,
                 "profile2": profile2})
    client.run("create . --name=pkg --version=0.1 -pr=profile1")
    client.assert_listed_binary({"pkg/0.1": ("7501c16e6c5c93e534dd760829859340e2dc73bc", "Build")})
    client.run("create . --name=pkg --version=0.1 -pr=profile2")
    client.assert_listed_binary({"pkg/0.1": ("4eb2bd276f75d2df8fa0f4b58bd86014b7f51693", "Build")})


def test_json_output(client):
    client.run("create . --name=pkg --version=0.1 -c user.myconf:myitem=1 --format=json")
    graph = json.loads(client.stdout)
    assert graph["graph"]["nodes"]["1"]["info"]["conf"] == {'user.myconf:myitem': 1}
