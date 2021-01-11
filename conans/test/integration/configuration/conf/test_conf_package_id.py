import textwrap

import pytest

from conans.test.utils.tools import TestClient


@pytest.fixture
def client():
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conans import ConanFile

        class Pkg(ConanFile):
            def package_id(self):
                self.info.conf = self.conf
        """)
    client.save({"conanfile.py": conanfile})
    return client


def test_package_id(client):
    profile1 = textwrap.dedent("""\
        [conf]
        tools.microsoft:msbuild_verbosity=Quiet""")
    profile2 = textwrap.dedent("""\
        [conf]
        tools.microsoft:msbuild_verbosity=Minimal""")
    client.save({"profile1": profile1,
                 "profile2": profile2})
    client.run("create . pkg/0.1@ -pr=profile1")
    assert "pkg/0.1:b40df771e875672867408f9edf54bec0c2c361a7 - Build" in client.out
    client.run("create . pkg/0.1@ -pr=profile2")
    assert "pkg/0.1:017c055fc7833bf6a7836211a26727533237071d - Build" in client.out
