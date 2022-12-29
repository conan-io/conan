import os
import platform
import shutil
import unittest

import pytest


from conans.test.assets.cpp_test_files import cpp_hello_conan_files
from conans.test.utils.tools import TestClient, TestServer
from conans.util.files import rmdir


@pytest.mark.slow
class SharedChainTest(unittest.TestCase):

    def setUp(self):
        self.servers = {"default": TestServer()}

    def _export_upload(self, name, version=None, deps=None):
        conan = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})
        files = cpp_hello_conan_files(name, version, deps, static=False)
        conan.save(files)

        conan.run("create . lasote/stable")
        conan.run("upload * --all --confirm")
        conan.run("remove * -f")
        rmdir(conan.current_folder)
        shutil.rmtree(conan.cache.store, ignore_errors=True)

    def test_uploaded_chain(self):
        self._export_upload("Hello0", "0.1")
        self._export_upload("Hello1", "0.1", ["Hello0/0.1@lasote/stable"])

        client = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})
        files = cpp_hello_conan_files("Hello2", "0.1", ["Hello1/0.1@lasote/stable"], static=True)
        c = files["conanfile.py"]
        c = c.replace("def imports(self):", "def imports(self):\n"
                                            '        self.copy(pattern="*.so", dst=".", src="lib")')
        files["conanfile.py"] = c
        client.save(files)

        client.run("install .")
        client.run("build .")
        ld_path = (
            "LD_LIBRARY_PATH='{}' ".format(client.current_folder)
            if platform.system() != "Windows"
            else ""
        )
        cmd_path = os.sep.join([".", "bin", "say_hello"])
        command = ld_path + cmd_path

        client.run_command(command)
        self.assertEqual(['Hello Hello2', 'Hello Hello1', 'Hello Hello0'],
                         str(client.out).splitlines()[-3:])
