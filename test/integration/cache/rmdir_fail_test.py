import os
import platform

import pytest

from conan.test.utils.tools import TestClient, GenConanfile


@pytest.mark.skipif(platform.system() != "Windows", reason="needs windows")
def test_fail_rmdir():
    client = TestClient()
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . --name=mypkg --version=0.1 --user=lasote --channel=testing")
    build_folder = client.created_layout().build()
    f = open(os.path.join(build_folder, "myfile"), "wb")
    f.write(b"Hello world")
    client.run("install --requires=mypkg/0.1@lasote/testing --build=*", assert_error=True)
    assert "ERROR: Couldn't remove folder" in client.out
