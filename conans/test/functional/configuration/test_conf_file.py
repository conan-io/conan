import textwrap

import pytest

from conans.test.utils.tools import TestClient
from conans.util.files import save


@pytest.fixture
def client():
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conans import ConanFile

        class Pkg(ConanFile):
            def generate(self):
                for k, conf in self.conf.items():
                    for name, value in conf.items():
                        self.output.info("{}${}${}".format(k, name, value))
        """)
    client.save({"conanfile.py": conanfile})
    return client


def test_msbuild_config(client):
    conf = textwrap.dedent("""\
        tools.microsoft.MSBuild:verbosity=Minimal
        """)
    save(client.cache.new_config_path, conf)
    client.run("create . pkg/0.1@")
    assert "pkg/0.1: tools.microsoft.MSBuild$verbosity$Minimal" in client.out
