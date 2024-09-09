import os
import shutil

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def test_db_error():
    # https://github.com/conan-io/conan/issues/14517
    c = TestClient(default_server_user=True)
    c.save({"liba/conanfile.py": GenConanfile("liba", "0.1")})
    c.run("create liba")
    c.run("install --requires=liba/0.1 --format=json", redirect_stdout="graph.json")
    c.run("list --graph=graph.json --format=json", redirect_stdout="installed.json")
    c.run("upload --list=installed.json -r=default --format=json -c", redirect_stdout="upload.json")

    c2 = TestClient(servers=c.servers, inputs=["admin", "password"])
    shutil.copy(os.path.join(c.current_folder, "upload.json"), c2.current_folder)
    c2.run("download --list=upload.json -r=default --format=json")
    # This used to crash
    assert "liba/0.1: Downloaded package revision" in c2.out
