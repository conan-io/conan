import json
import os
import textwrap

import pytest

from conan.test.utils.tools import TestClient


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
    client.run("install --requires=dep/0.1 -c tools.build:download_source=True --format=json")
    assert "RUNNING SOURCE" in client.out
    graph = json.loads(client.stdout)
    zlib = graph["graph"]["nodes"]["1"]
    assert os.path.exists(zlib["source_folder"])
    client.run("install --requires=dep/0.1 -c tools.build:download_source=True --format=json")
    assert "RUNNING SOURCE" not in client.out
    graph = json.loads(client.stdout)
    zlib = graph["graph"]["nodes"]["1"]
    assert os.path.exists(zlib["source_folder"])


def test_info(client):
    client.run("graph info --requires=dep/0.1")
    assert "RUNNING SOURCE" not in client.out
    # Even if the package is to be built, it shouldn't download sources unless the conf is defined
    client.run("graph info --requires=dep/0.1 --build=dep*")
    assert "RUNNING SOURCE" not in client.out
    client.run("graph info --requires=dep/0.1 -c tools.build:download_source=True")
    assert "RUNNING SOURCE" in client.out
    client.run("graph info --requires=dep/0.1 -c tools.build:download_source=True")
    assert "RUNNING SOURCE" not in client.out


def test_info_editable():
    """ graph info for editable shouldn't crash, but it also shoudn't do anythin
    # https://github.com/conan-io/conan/issues/15003
    """
    c = TestClient()
    dep = textwrap.dedent("""
        from conan import ConanFile

        class Dep(ConanFile):
            name = "dep"
            version = "0.1"

            def source(self):
                self.output.info("RUNNING SOURCE!!")
            """)

    c.save({"conanfile.py": dep})
    c.run("editable add .")
    c.run("graph info --requires=dep/0.1")
    assert "RUNNING SOURCE" not in c.out
    c.run("graph info --requires=dep/0.1 -c tools.build:download_source=True")
    assert "RUNNING SOURCE" not in c.out  # BUT it doesn't crash, it used to crash
