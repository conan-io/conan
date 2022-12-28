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
    client.assert_listed_binary({"pkg/0.1": ("f34214fcde48b6a07353cfe1dbd452cdf01a098c", "Build")})
    client.run("create . --name=pkg --version=0.1 -pr=profile2")
    client.assert_listed_binary({"pkg/0.1": ("1db44e3df6a7a86a169026273f283074d69dfa81", "Build")})
