import os

import pytest

from conans.model.manifest import FileTreeManifest
from conans.model.ref import ConanFileReference
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


@pytest.mark.parametrize("relative_path", [False, True])
def test_basic(relative_path):
    client = TestClient()
    source_folder = os.path.join(client.current_folder, "source")
    files = {"conanfile.py": GenConanfile().with_exports("*"),
             "main.cpp": "mymain"}
    client.save(files, path=source_folder)
    if relative_path:
        with client.chdir("current"):
            client.run("export ../source hello/0.1@lasote/stable")
    else:
        client.run("export source hello/0.1@lasote/stable")

    # The result should be the same in both cases
    ref = ConanFileReference("hello", "0.1", "lasote", "stable")
    reg_path = client.cache.package_layout(ref).export()
    manif = FileTreeManifest.load(reg_path)

    assert '%s: A new conanfile.py version was exported' % str(ref) in client.out
    assert '%s: Folder: %s' % (str(ref), reg_path) in client.out

    for name in list(files.keys()):
        assert os.path.exists(os.path.join(reg_path, name))

    expected_sums = {'conanfile.py': '1b7c687fffb8544bd2de497cd7a6eee6',
                     'main.cpp': '76c0a7a9d385266e27d69d3875f6ac19'}
    assert expected_sums == manif.file_sums


@pytest.mark.parametrize("relative_path", [False, True])
def test_path(relative_path):
    client = TestClient()
    if relative_path:
        client.save({"conan/conanfile.py": GenConanfile().with_exports("../source*"),
                     "source/main.cpp": "mymain"})
        with client.chdir("current"):
            client.run("export ../conan hello/0.1@lasote/stable")
    else:
        client.save({"current/conanfile.py": GenConanfile().with_exports("../source*"),
                     "source/main.cpp": "mymain"})
        with client.chdir("current"):
            client.run("export . hello/0.1@lasote/stable")

    ref = ConanFileReference("hello", "0.1", "lasote", "stable")
    reg_path = client.cache.package_layout(ref).export()
    manif = FileTreeManifest.load(reg_path)

    for name in ['conanfile.py', 'conanmanifest.txt', 'source/main.cpp']:
        assert os.path.exists(os.path.join(reg_path, name))

    expected_sums = {'conanfile.py': '718d94ef217b17297e10d60f1132ccf5',
                     'source/main.cpp': '76c0a7a9d385266e27d69d3875f6ac19'}
    assert expected_sums == manif.file_sums
