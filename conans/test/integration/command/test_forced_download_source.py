import textwrap

import pytest

from conans.test.utils.tools import TestClient


@pytest.fixture()
def client():
    c = TestClient(default_server_user=True)
    dep = textwrap.dedent("""
        from conan import ConanFile
        class Dep(ConanFile):
            name = "dep"
            version = "0.1"
            def source(self):
                self.output.info("RUNNING SOURCE!!")
            """)

    c.save({"dep/conanfile.py": dep})
    c.run("create dep")
    c.run("upload * -c -r=default")
    c.run("remove * -c")
    return c


def test_install(client):
    client.run("install --requires=dep/0.1")
    assert "RUNNING SOURCE" not in client.out
    client.run("install --requires=dep/0.1 -c tools.build:download_source=True")
    assert "RUNNING SOURCE" in client.out
    client.run("install --requires=dep/0.1 -c tools.build:download_source=True")
    assert "RUNNING SOURCE" not in client.out


def test_info(client):
    client.run("graph info --requires=dep/0.1")
    assert "RUNNING SOURCE" not in client.out
    client.run("graph info --requires=dep/0.1 -c tools.build:download_source=True")
    assert "RUNNING SOURCE" in client.out
    client.run("graph info --requires=dep/0.1 -c tools.build:download_source=True")
    assert "RUNNING SOURCE" not in client.out
