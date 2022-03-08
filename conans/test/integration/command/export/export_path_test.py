import os

import pytest

from conans.model.manifest import FileTreeManifest
from conans.model.recipe_ref import RecipeReference
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
            client.run("export ../source --name=hello --version=0.1 --user=lasote --channel=stable")
    else:
        client.run("export source --name=hello --version=0.1 --user=lasote --channel=stable")

    # The result should be the same in both cases
    ref = RecipeReference("hello", "0.1", "lasote", "stable")
    latest_rrev = client.cache.get_latest_recipe_reference(ref)
    ref_layoyt = client.cache.ref_layout(latest_rrev)
    reg_path = ref_layoyt.export()
    manif = FileTreeManifest.load(reg_path)

    assert '%s: A new conanfile.py version was exported' % str(ref) in client.out
    assert '%s: Folder: %s' % (str(ref), reg_path) in client.out

    for name in list(files.keys()):
        assert os.path.exists(os.path.join(reg_path, name))

    expected_sums = {'conanfile.py': '7fbb7e71f5b665780ff8c407fe0b1f9e',
                     'main.cpp': '76c0a7a9d385266e27d69d3875f6ac19'}
    assert expected_sums == manif.file_sums


@pytest.mark.parametrize("relative_path", [False, True])
def test_path(relative_path):
    client = TestClient()
    if relative_path:
        client.save({"conan/conanfile.py": GenConanfile().with_exports("../source*"),
                     "source/main.cpp": "mymain"})
        with client.chdir("current"):
            client.run("export ../conan --name=hello --version=0.1 --user=lasote --channel=stable")
    else:
        client.save({"current/conanfile.py": GenConanfile().with_exports("../source*"),
                     "source/main.cpp": "mymain"})
        with client.chdir("current"):
            client.run("export . --name=hello --version=0.1 --user=lasote --channel=stable")

    ref = RecipeReference("hello", "0.1", "lasote", "stable")
    latest_rrev = client.cache.get_latest_recipe_reference(ref)
    ref_layoyt = client.cache.ref_layout(latest_rrev)
    reg_path = ref_layoyt.export()
    manif = FileTreeManifest.load(reg_path)

    for name in ['conanfile.py', 'conanmanifest.txt', 'source/main.cpp']:
        assert os.path.exists(os.path.join(reg_path, name))

    expected_sums = {'conanfile.py': 'bebe98b13c5a958732a6bbe2a9d068f3',
                     'source/main.cpp': '76c0a7a9d385266e27d69d3875f6ac19'}
    assert expected_sums == manif.file_sums
