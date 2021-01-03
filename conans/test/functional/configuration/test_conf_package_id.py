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
        tools.microsoft.MSBuild:verbosity=Quiet""")
    profile2 = textwrap.dedent("""\
        [conf]
        tools.microsoft.MSBuild:verbosity=Minimal""")
    client.save({"profile1": profile1,
                 "profile2": profile2})
    client.run("create . pkg/0.1@ -pr=profile1")
    assert "pkg/0.1:51aab6e93977427e069d939041a2b92920982198 - Build" in client.out
    client.run("create . pkg/0.1@ -pr=profile2")
    assert "pkg/0.1:53697b10d2341b57b4027c29688ba0ac89b7f7ae - Build" in client.out
