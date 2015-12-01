import unittest
from conans.test.tools import TestServer, TestClient
import platform
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.model.ref import ConanFileReference
from nose.plugins.attrib import attr
from conans.util.files import rmdir
import shutil


@attr("slow")
class SharedChainTest(unittest.TestCase):

    def setUp(self):
        self.static = False
        test_server = TestServer([("*/*@*/*", "*")],  # read permissions
                                 [],  # write permissions
                                 users={"lasote": "mypass"})  # exported users and passwords
        self.servers = {"default": test_server}

    def _export_upload(self, name, version=None, deps=None):
        conan = TestClient(servers=self.servers, users=[("lasote", "mypass")])
        files = cpp_hello_conan_files(name, version, deps, static=self.static)
        conan_ref = ConanFileReference(name, version, "lasote", "stable")
        conan.save(files, clean_first=True)
        conan.run("export lasote/stable")
        conan.run("install '%s' -o static=False -o language=0 --build missing" % str(conan_ref))
        conan.run("upload %s --all" % str(conan_ref))
        rmdir(conan.current_folder)
        shutil.rmtree(conan.paths.store, ignore_errors=True)

    def uploaded_chain_test(self):
        self._export_upload("Hello0", "0.1")
        self._export_upload("Hello1", "0.1", ["Hello0/0.1@lasote/stable"])

        client = TestClient(servers=self.servers, users=[("lasote", "mypass")])  # Mocked userio
        files2 = cpp_hello_conan_files("Hello2", "0.1", ["Hello1/0.1@lasote/stable"], static=True)
        client.save(files2)

        client.run("install . --build missing")
        client.run("build .")
        command = "say_hello" if platform.system() == "Windows" else "./say_hello"

        client.runner(command, client.current_folder)
        self.assertEqual(['Hello Hello2', 'Hello Hello1', 'Hello Hello0'],
                         str(client.user_io.out).splitlines()[-3:])
