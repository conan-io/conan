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
    client.assert_listed_binary({"pkg/0.1": ("bf9f277ff9c5ce88c27d42e2de02d8ee3433ddd9", "Build")})
    client.run("create . --name=pkg --version=0.1 -pr=profile2")
    client.assert_listed_binary({"pkg/0.1": ("aafb08585a95c8a51b765f758507cbee1e680867", "Build")})
