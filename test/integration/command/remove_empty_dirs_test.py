import os

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


class TestRemoveEmptyDirs:

    def test_basic(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile("hello", "0.1")})
        client.run("export . --user=lasote --channel=stable")
        ref_layout = client.exported_layout()
        assert os.path.exists(ref_layout.base_folder)
        client.run("remove hello* -c")
        assert not os.path.exists(ref_layout.base_folder)

    def test_shared_folder(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile("hello", "0.1")})
        client.run("export . --user=lasote --channel=stable")
        ref_layout = client.exported_layout()
        assert os.path.exists(ref_layout.base_folder)
        client.run("export . --user=lasote2 --channel=stable")
        ref_layout2 = client.exported_layout()
        assert os.path.exists(ref_layout2.base_folder)
        client.run("remove hello/0.1@lasote/stable -c")
        assert not os.path.exists(ref_layout.base_folder)
        assert os.path.exists(ref_layout2.base_folder)
