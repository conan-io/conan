import os
import textwrap
import json
import pytest

from conan.internal.paths import CONANFILE
from conan.test.utils.tools import TestClient
from conan.internal.cache.conan_reference_layout import EXPORT_FOLDER

conanfile_py = """
from conan import ConanFile

class AConan(ConanFile):
    name = "package"
    version = "0.1.0"
    short_paths=False
"""

with_deps_path_file = """
from conan import ConanFile

class BConan(ConanFile):
    name = "package2"
    version = "0.2.0"
    requires = "package/0.1.0@user/testing"
"""

deps_txt_file = """
[requires]
package2/0.2.0@user/testing
"""


@pytest.fixture()
def client_deps():
    client = TestClient()
    client.save({CONANFILE: conanfile_py})
    client.run(f"export . --user=user --channel=testing")
    client.save({CONANFILE: with_deps_path_file}, clean_first=True)
    client.run(f"export . --user=user --channel=testing")
    client.save({'conanfile.txt': deps_txt_file}, clean_first=True)
    return client


def test_basic():
    client = TestClient()
    client.save({CONANFILE: conanfile_py})
    client.run(f"export . --user=user --channel=testing")
    client.run(f"graph info --requires=package/0.1.0@user/testing --format=json")
    nodes = json.loads(client.stdout)["graph"]["nodes"]
    assert client.cache_folder in nodes["1"]["recipe_folder"]
    assert os.path.basename(nodes["1"]["recipe_folder"]).strip() == EXPORT_FOLDER
    assert nodes["1"]["source_folder"] is None
    assert nodes["1"]["build_folder"] is None
    assert nodes["1"]["package_folder"] is None


def test_build_id():
    # https://github.com/conan-io/conan/issues/6915
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class Pkg(ConanFile):
            options = {"myOption": [True, False]}
            def build_id(self):
                self.info_build.options.myOption = "Any"
        """)
    client.save({CONANFILE: conanfile})
    client.run(f"export . --name=pkg --version=0.1 --user=user --channel=testing")
    client.run(f"graph info --requires=pkg/0.1@user/testing -o pkg/*:myOption=True")
    out = str(client.out).replace("\\", "/")
    assert "package_id: b868c8ab4ae6ddccfe19fabd62a5e180d4b18a2b" in out
    assert "build_id: d5d6fc54af6f589e338090910ac18c848a87720d" in out

    client.run("graph info --requires=pkg/0.1@user/testing -o pkg/*:myOption=False")
    out = str(client.out).replace("\\", "/")
    assert "package_id: 41e2e23ac9570fd23f421bcd0cf9e5cbab49e6ee" in out
    assert "build_id: d5d6fc54af6f589e338090910ac18c848a87720d" in out


def test_deps_basic(client_deps):
    for ref in [f"--requires=package2/0.2.0@user/testing", "conanfile.txt"]:
        client_deps.run(f"graph info {ref} --format=json")
        nodes = json.loads(client_deps.stdout)
        found_ref = False
        assert len(nodes["graph"]["nodes"]) == 3

        for _, node in nodes["graph"]["nodes"].items():
            if node["ref"] == "conanfile":
                assert node["source_folder"] is None
            else:
                assert client_deps.cache_folder in node["recipe_folder"]
                assert os.path.basename(node["recipe_folder"]).strip() == EXPORT_FOLDER
            assert node["source_folder"] is None
            assert node["build_folder"] is None
            assert node["package_folder"] is None
            found_ref = found_ref or "package/0.1.0@user/testing" in node["ref"]
        assert found_ref


def test_deps_specific_information(client_deps):
    client_deps.run("graph info . --package-filter package/* --format=json")
    nodes = json.loads(client_deps.stdout)["graph"]["nodes"]
    assert len(nodes) == 1
    assert "package/0.1.0@user/testing" in nodes["2"]["ref"]
    assert nodes["2"]["source_folder"] is None
    assert nodes["2"]["build_folder"] is None
    assert nodes["2"]["package_folder"] is None

    client_deps.run("graph info . --package-filter package* --format=json")
    nodes = json.loads(client_deps.stdout)["graph"]["nodes"]
    assert len(nodes) == 2
    assert "package2/0.2.0@user/testing" in nodes["1"]["ref"]
    assert nodes["1"]["source_folder"] is None
    assert nodes["1"]["build_folder"] is None
    assert nodes["1"]["package_folder"] is None
    assert "package/0.1.0@user/testing" in nodes["2"]["ref"]
    assert nodes["2"]["source_folder"] is None
    assert nodes["2"]["build_folder"] is None
    assert nodes["2"]["package_folder"] is None


def test_single_field():
    client = TestClient()
    client.save({CONANFILE: conanfile_py})
    client.run(f"export . --user=user --channel=testing")
    client.run(f"graph info --requires package/0.1.0@user/testing --format=json")
    nodes = json.loads(client.stdout)["graph"]["nodes"]
    assert len(nodes) == 2
    assert "package/0.1.0@user/testing" in nodes["1"]["ref"]
    assert nodes["1"]["source_folder"] is None
    assert nodes["1"]["build_folder"] is None
    assert nodes["1"]["package_folder"] is None


def test_direct_conanfile():
    client = TestClient()
    client.save({CONANFILE: conanfile_py})
    client.run("graph info .")
    output = client.out
    assert "export_folder" not in output
    assert "source_folder: None" in output
    assert "build_folder: None" in output
    assert "package_folder: None" in output
