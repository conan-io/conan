import os
import platform

import pytest

from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient, GenConanfile


@pytest.mark.skipif(platform.system() != "Windows", reason="needs windows")
def test_fail_rmdir():
    client = TestClient()
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . MyPkg/0.1@lasote/testing")
    ref = ConanFileReference.loads("MyPkg/0.1@lasote/testing")
    build_folder = client.get_latest_pkg_layout(ref).build()
    f = open(os.path.join(build_folder, "myfile"), "wb")
    f.write(b"Hello world")
    client.run("install MyPkg/0.1@lasote/testing --build", assert_error=True)
    assert "Couldn't remove folder, might be busy or open" in client.out
