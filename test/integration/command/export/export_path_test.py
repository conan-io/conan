import os
import textwrap

import pytest

from conans.model.manifest import FileTreeManifest
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


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
    ref_layoyt = client.exported_layout()
    ref = ref_layoyt.reference
    reg_path = ref_layoyt.export()
    manif = FileTreeManifest.load(reg_path)

    assert '%s: Exported' % str(ref) in client.out
    assert '%s: Exported to cache folder: %s' % (str(ref), reg_path) in client.out

    for name in list(files.keys()):
        assert os.path.exists(os.path.join(reg_path, name))

    expected_sums = {'conanfile.py': '7fbb7e71f5b665780ff8c407fe0b1f9e',
                     'main.cpp': '76c0a7a9d385266e27d69d3875f6ac19'}
    assert expected_sums == manif.file_sums


@pytest.mark.parametrize("relative_path", [False, True])
def test_path(relative_path):
    client = TestClient()
    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import copy
        class Pkg(ConanFile):
            def export(self):
                copy(self, "*", src=os.path.join(self.recipe_folder, "..", "source"),
                     dst=os.path.join(self.export_folder, "source"))
            """)
    if relative_path:
        client.save({"conan/conanfile.py": conanfile,
                     "source/main.cpp": "mymain"})
        with client.chdir("current"):
            client.run("export ../conan --name=hello --version=0.1 --user=lasote --channel=stable")
    else:
        client.save({"current/conanfile.py": conanfile,
                     "source/main.cpp": "mymain"})
        with client.chdir("current"):
            client.run("export . --name=hello --version=0.1 --user=lasote --channel=stable")
    ref_layoyt = client.exported_layout()
    reg_path = ref_layoyt.export()
    manif = FileTreeManifest.load(reg_path)

    for name in ['conanfile.py', 'conanmanifest.txt', 'source/main.cpp']:
        assert os.path.exists(os.path.join(reg_path, name))

    expected_sums = {'conanfile.py': '6cdb33126a0408bffc0ad0ada66cb061',
                     'source/main.cpp': '76c0a7a9d385266e27d69d3875f6ac19'}
    assert expected_sums == manif.file_sums
