import unittest
from conans.test.utils.tools import TestServer, TestClient
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.model.ref import ConanFileReference
from nose.plugins.attrib import attr
from conans.util.files import rmdir
import shutil
import os


@attr("slow")
class SharedChainTest(unittest.TestCase):

    def setUp(self):
        self.static = False
        test_server = TestServer()
        self.servers = {"default": test_server}

    def _export_upload(self, name, version=None, deps=None):
        conan = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})
        dll_export = conan.default_compiler_visual_studio
        files = cpp_hello_conan_files(name, version, deps, static=False, dll_export=dll_export)
        conan_ref = ConanFileReference(name, version, "lasote", "stable")
        conan.save(files, clean_first=True)

        conan.run("export lasote/stable")
        conan.run("install '%s' --build missing" % str(conan_ref))
        conan.run("upload %s --all" % str(conan_ref))
        rmdir(conan.current_folder)
        shutil.rmtree(conan.paths.store, ignore_errors=True)

    def uploaded_chain_test(self):
        self._export_upload("Hello0", "0.1")
        self._export_upload("Hello1", "0.1", ["Hello0/0.1@lasote/stable"])

        client = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})
        files2 = cpp_hello_conan_files("Hello2", "0.1", ["Hello1/0.1@lasote/stable"], static=True)
        client.save(files2)

        client.run("install . --build missing")
        client.run("build .")
        command = os.sep.join([".", "bin", "say_hello"])

        client.runner(command, cwd=client.current_folder)
        self.assertEqual(['Hello Hello2', 'Hello Hello1', 'Hello Hello0'],
                         str(client.user_io.out).splitlines()[-3:])
