import os
import shutil
import unittest

import pytest
from nose.plugins.attrib import attr

from conans.test.assets.cpp_test_files import cpp_hello_conan_files
from conans.test.utils.tools import TestClient, TestServer
from conans.util.files import rmdir


@attr("slow")
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

    @pytest.mark.tool_compiler
    def test_uploaded_chain(self):
        self._export_upload("Hello0", "0.1")
        self._export_upload("Hello1", "0.1", ["Hello0/0.1@lasote/stable"])

        client = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})
        files = cpp_hello_conan_files("Hello2", "0.1", ["Hello1/0.1@lasote/stable"], static=True)
        client.save(files)

        client.run("install .")
        client.run("build .")
        command = os.sep.join([".", "bin", "say_hello"])
        client.run_command(command)
        self.assertEqual(['Hello Hello2', 'Hello Hello1', 'Hello Hello0'],
                         str(client.out).splitlines()[-3:])
