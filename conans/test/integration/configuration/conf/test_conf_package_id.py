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
        tools.microsoft.msbuild:verbosity=Quiet""")
    profile2 = textwrap.dedent("""\
        [conf]
        tools.microsoft.msbuild:verbosity=Minimal""")
    client.save({"profile1": profile1,
                 "profile2": profile2})
    client.run("create . pkg/0.1@ -pr=profile1")
    assert "pkg/0.1:b85ef030da903577bd87d1c92c0524c9c96212b5 - Build" in client.out
    client.run("create . pkg/0.1@ -pr=profile2")
    assert "pkg/0.1:7d2f1590113db99bcd08a4ebd4c841cc0a2e7020 - Build" in client.out
    client.run("create . pkg/0.1@ -c tools.microsoft.msbuild:verbosity=Detailed")
    assert "pkg/0.1:a2e8034244a388f79b31ebec1ddb991bd7b91f48 - Build" in client.out
