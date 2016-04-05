import unittest
from conans.test.tools import TestServer, TestClient
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.model.ref import ConanFileReference
from nose.plugins.attrib import attr
from conans.model.build_info import DepsCppInfo
from conans.util.files import load
import os
from conans.paths import BUILD_INFO, CONANFILE, BUILD_INFO_CMAKE


@attr("slow")
class DiamondTest(unittest.TestCase):

    def setUp(self):
        test_server = TestServer([("*/*@*/*", "*")],  # read permissions
                                 [],  # write permissions
                                 users={"lasote": "mypass"})  # exported users and passwords
        self.servers = {"default": test_server}
        self.conan = TestClient(servers=self.servers, users={"default":[("lasote", "mypass")]})

    def _export_upload(self, name, version=None, deps=None):
        files = cpp_hello_conan_files(name, version, deps, need_patch=True)
        conan_ref = ConanFileReference(name, version, "lasote", "stable")
        self.conan.save(files, clean_first=True)
        self.conan.run("export lasote/stable")
        self.conan.run("upload %s" % str(conan_ref))

    def _check_individual_deps(self, client):
        self.assertIn("INCLUDE [", client.user_io.out)
        self.assertIn(".conan/data/Hello0/0.1/lasote/stable", client.user_io.out)
        build_file = os.path.join(client.current_folder, BUILD_INFO)
        content = load(build_file)
        cmakebuildinfo = load(os.path.join(client.current_folder, BUILD_INFO_CMAKE))
        self.assertIn("set(CONAN_LIBS helloHello3 helloHello1 helloHello2 helloHello0",
                      cmakebuildinfo)
        deps_cpp_info = DepsCppInfo.loads(content)
        self.assertEqual(len(deps_cpp_info.include_paths), 4)
        for dep in ("Hello3", "Hello2", "Hello1", "Hello0"):
            self.assertEqual(len(deps_cpp_info[dep].include_paths), 1)
            self.assertEqual(len(deps_cpp_info[dep].lib_paths), 1)
            self.assertEqual(deps_cpp_info[dep].libs, ["hello%s" % dep])
        build_file = os.path.join(client.current_folder, BUILD_INFO_CMAKE)
        content = load(build_file)
        for dep in ("Hello3", "Hello2", "Hello1", "Hello0"):
            self.assertEqual(len(deps_cpp_info[dep].include_paths), 1)
            self.assertIn("set(CONAN_INCLUDE_DIRS_%s " % dep.upper(), content)
            self.assertIn("set(CONAN_LIBS_%s hello%s)" % (dep.upper(), dep), content)

    def reuse_test(self):
        self._export_upload("Hello0", "0.1")
        self._export_upload("Hello1", "0.1", ["Hello0/0.1@lasote/stable"])
        self._export_upload("Hello2", "0.1", ["Hello0/0.1@lasote/stable"])
        self._export_upload("Hello3", "0.1", ["Hello1/0.1@lasote/stable",
                                              "Hello2/0.1@lasote/stable"])

        client = TestClient(servers=self.servers, users={"default":[("lasote", "mypass")]})  # Mocked userio
        files3 = cpp_hello_conan_files("Hello4", "0.1", ["Hello3/0.1@lasote/stable"])

        # Add some stuff to base project conanfile to test further the individual
        # flags in build_info (txt, cmake) files
        content = files3[CONANFILE]
        content = content.replace("generators =", 'generators = "txt",')
        content = content.replace("def build(self):",
                                            "def build(self):\n        "
                                            "self.output.info('INCLUDE %s' "
                                            "% self.deps_cpp_info['Hello0'].include_paths)")
        files3[CONANFILE] = content
        client.save(files3)

        client.run("install . --build missing")
        client.run("build .")
        self._check_individual_deps(client)

        command = os.sep.join([".", "bin", "say_hello"])
        client.runner(command, cwd=client.current_folder)
        self.assertEqual(['Hello Hello4', 'Hello Hello3', 'Hello Hello1', 'Hello Hello0',
                          'Hello Hello2', 'Hello Hello0'],
                         str(client.user_io.out).splitlines()[-6:])

        files3 = cpp_hello_conan_files("Hello4", "0.1", ["Hello3/0.1@lasote/stable"], language=1)
        client.save(files3, clean_first=True)
        client.run("install . --build missing")
        client.run("build .")

        client.runner(command, cwd=client.current_folder)
        self.assertEqual(['Hola Hello4', 'Hola Hello3', 'Hola Hello1', 'Hola Hello0',
                          'Hola Hello2', 'Hola Hello0'],
                         str(client.user_io.out).splitlines()[-6:])

        # Try to upload and reuse the binaries
        client.run("upload Hello3/0.1@lasote/stable --all")
        self.assertEqual(str(client.user_io.out).count("Uploading package"), 2)
        client.run("upload Hello1/0.1@lasote/stable --all")
        self.assertEqual(str(client.user_io.out).count("Uploading package"), 2)
        client.run("upload Hello2/0.1@lasote/stable --all")
        self.assertEqual(str(client.user_io.out).count("Uploading package"), 2)
        client.run("upload Hello0/0.1@lasote/stable --all")
        self.assertEqual(str(client.user_io.out).count("Uploading package"), 2)

        client2 = TestClient(servers=self.servers, users={"default":[("lasote", "mypass")]})  # Mocked userio
        files3 = cpp_hello_conan_files("Hello4", "0.1", ["Hello3/0.1@lasote/stable"])
        client2.save(files3)
        client2.run("install . --build missing")
        client2.run("build .")

        self.assertNotIn("libhello0.a", client2.user_io.out)
        self.assertNotIn("libhello1.a", client2.user_io.out)
        self.assertNotIn("libhello2.a", client2.user_io.out)
        self.assertNotIn("libhello3.a", client2.user_io.out)
        client2.runner(command, cwd=client2.current_folder)
        self.assertEqual(['Hello Hello4', 'Hello Hello3', 'Hello Hello1', 'Hello Hello0',
                          'Hello Hello2', 'Hello Hello0'],
                         str(client2.user_io.out).splitlines()[-6:])

        files3 = cpp_hello_conan_files("Hello4", "0.1", ["Hello3/0.1@lasote/stable"], language=1)
        client2.save(files3, clean_first=True)
        client2.run("install . --build missing")
        client2.run("build .")
        self.assertNotIn("libhello0.a", client2.user_io.out)
        self.assertNotIn("libhello1.a", client2.user_io.out)
        self.assertNotIn("libhello2.a", client2.user_io.out)
        self.assertNotIn("libhello3.a", client2.user_io.out)
        client2.runner(command, cwd=client2.current_folder)
        self.assertEqual(['Hola Hello4', 'Hola Hello3', 'Hola Hello1', 'Hola Hello0',
                          'Hola Hello2', 'Hola Hello0'],
                         str(client2.user_io.out).splitlines()[-6:])
