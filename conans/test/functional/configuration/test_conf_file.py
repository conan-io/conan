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
                        self.output.info("CONFIG:{}${}${}".format(k, name, value))
        """)
    client.save({"conanfile.py": conanfile})
    return client


def test_new_config_file(client):
    conf = textwrap.dedent("""\
        tools.microsoft.MSBuild:verbosity=Minimal
        user.mycompany.MyHelper:myconfig=myvalue
        cache:no_locks=True
        cache:read_only=True
        """)
    save(client.cache.new_config_path, conf)
    client.run("install .")
    print(client.out)
    assert "conanfile.py: CONFIG:tools.microsoft.MSBuild$verbosity$Minimal" in client.out
    assert "conanfile.py: CONFIG:user.mycompany.MyHelper$myconfig$myvalue" in client.out
    assert "no_locks" not in client.out
    assert "read_only" not in client.out
