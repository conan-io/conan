import textwrap

import pytest

from conans.test.utils.tools import TestClient


@pytest.fixture
def client():
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile

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
    client.run("create . --name=pkg --version=0.1 -pr=profile1")
    client.assert_listed_binary({"pkg/0.1": ("a3122d010800dcb58876215fc9da0874b486165c", "Build")})
    client.run("create . --name=pkg --version=0.1 -pr=profile2")
    client.assert_listed_binary({"pkg/0.1": ("b00c0fad28de4d64e6080815a67fc28aaab06440", "Build")})
