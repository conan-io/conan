import unittest
from conans.test.utils.tools import TestClient, TestServer
from conans.model.ref import ConanFileReference
import os
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.paths import CONANINFO, BUILD_INFO_CMAKE
from conans.util.files import load
from conans.model.info import ConanInfo
from nose.plugins.attrib import attr


@attr("slow")
class PrivateDepsTest(unittest.TestCase):

    def setUp(self):
        test_server = TestServer()
        self.servers = {"default": test_server}
        self.client = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})

    def _export_upload(self, name=0, version=None, deps=None, msg=None, static=True, build=True,
                       upload=True):
        dll_export = self.client.default_compiler_visual_studio and not static
        files = cpp_hello_conan_files(name, version, deps, msg=msg, static=static,
                                      private_includes=True, dll_export=dll_export, build=build,
                                      cmake_targets=False)
        conan_ref = ConanFileReference(name, version, "lasote", "stable")
        self.client.save(files, clean_first=True)
        self.client.run("export . lasote/stable")
        if upload:
            self.client.run("upload %s" % str(conan_ref))

    def _export(self, name=0, version=None, deps=None):
        files = cpp_hello_conan_files(name, version, deps,
                                      private_includes=True, build=False,
                                      cmake_targets=True)
        self.client.save(files, clean_first=True)
        self.client.run("export . lasote/stable")

    def modern_cmake_test(self):
        self._export("glew", "0.1")
        self._export("glm", "0.1")
        self._export("gf", "0.1", deps=[("glm/0.1@lasote/stable", "private"),
                                        "glew/0.1@lasote/stable"])

        self._export("ImGuiTest", "0.1", deps=["glm/0.1@lasote/stable",
                                               "gf/0.1@lasote/stable"])

        # Consuming project
        self._export("Project", "0.1", deps=["ImGuiTest/0.1@lasote/stable"])

        # Build packages for both recipes
        self.client.run('install . --build=missing')
        conanbuildinfo_cmake = load(os.path.join(self.client.current_folder,
                                                 "conanbuildinfo.cmake"))
        conanbuildinfo_cmake = " ".join(conanbuildinfo_cmake.splitlines())
        self.assertIn("CONAN_PKG::gf PROPERTY INTERFACE_LINK_LIBRARIES "
                      "${CONAN_PACKAGE_TARGETS_GF}", conanbuildinfo_cmake)
        self.assertIn("CONAN_PKG::ImGuiTest PROPERTY INTERFACE_LINK_LIBRARIES "
                      "${CONAN_PACKAGE_TARGETS_IMGUITEST}", conanbuildinfo_cmake)

    def consumer_force_build_test(self):
        """If a conanfile requires another private conanfile, but in the install is forced
        the build, the private node has to be downloaded and built"""
        self._export_upload("Hello0", "0.1", build=False, upload=False)
        self._export_upload("Hello1", "0.1", deps=[("Hello0/0.1@lasote/stable", "private")],
                            build=False, upload=False)

        # Build packages for both recipes
        self.client.run('install Hello1/0.1@lasote/stable --build missing')

        # Upload them to remote
        self.client.run("upload Hello0/0.1@lasote/stable --all")
        self.client.run("upload Hello1/0.1@lasote/stable --all")

        # Remove local recipes and packages
        self.client.run('remove Hello* -f')

        # Install them without force build, private is not retrieved
        self.client.run('install Hello1/0.1@lasote/stable --build missing')
        # FIXME: recipe should not be retrieved either
        # self.assertNotIn("Hello0/0.1@lasote/stable", self.client.user_io.out)
        self.assertNotIn("Hello0/0.1@lasote/stable: Package installed", self.client.user_io.out)

        # Remove local recipes and packages
        self.client.run('remove Hello* -f')

        # Install them without force build, private is not retrieved
        self.client.run('install Hello1/0.1@lasote/stable ')
        self.assertNotIn("Hello0/0.1@lasote/stable: Package installed", self.client.user_io.out)

        # Remove local recipes and packages
        self.client.run('remove Hello* -f')

        # Install them without forcing build
        self.client.run('install Hello1/0.1@lasote/stable --build Hello1')
        self.assertIn("Hello0/0.1@lasote/stable: Package installed", self.client.user_io.out)
        self.assertIn("Hello1/0.1@lasote/stable: Building your package", self.client.user_io.out)

    def consumer_private_test(self):
        self._export_upload("Hello0", "0.1", build=False, upload=False)
        self._export_upload("Hello1", "0.1", deps=["Hello0/0.1@lasote/stable"],
                            build=False, upload=False)
        self._export_upload("Hello2", "0.1", deps=[("Hello1/0.1@lasote/stable", "private")],
                            build=False, upload=False)
        self._export_upload("Hello3", "0.1", deps=[("Hello2/0.1@lasote/stable"),
                                                   ],
                            build=False, upload=False)

        self.client.run('install . --build missing')
        self.assertIn("Hello0/0.1@lasote/stable: Generating the package", self.client.user_io.out)
        self.assertIn("Hello1/0.1@lasote/stable: Generating the package", self.client.user_io.out)
        self.assertIn("Hello2/0.1@lasote/stable: Generating the package", self.client.user_io.out)

        self.client.run("remove Hello0* -p -f ")
        self.client.run("remove Hello1* -p -f")
        self.client.run("search Hello0/0.1@lasote/stable")
        self.assertIn("There are no packages for pattern 'Hello0/0.1@lasote/stable'",
                      self.client.user_io.out)
        self.client.run("search Hello1/0.1@lasote/stable")
        self.assertIn("There are no packages for pattern 'Hello1/0.1@lasote/stable'",
                      self.client.user_io.out)

        self.client.run('install . --build missing')
        self.assertNotIn("Hello0/0.1@lasote/stable: Generating the package",
                         self.client.user_io.out)
        self.assertNotIn("Hello1/0.1@lasote/stable: Generating the package",
                         self.client.user_io.out)

    def reuse_test(self):
        self._export_upload("Hello0", "0.1")
        self._export_upload("Hello1", "0.1", deps=[("Hello0/0.1@lasote/stable", "private")],
                            static=False)

        client = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})
        files3 = cpp_hello_conan_files("Hello3", "0.1", ["Hello1/0.1@lasote/stable"])
        client.save(files3)

        client.run('install . --build missing')
        client.run('build .')

        # assert Hello3 only depends on Hello2, and Hello1
        build_info_cmake = load(os.path.join(client.current_folder, BUILD_INFO_CMAKE))
        # Ensure it does not depend on Hello0 to build, as private in dlls
        self.assertNotIn("Hello0", repr(build_info_cmake))

        command = os.sep.join([".", "bin", "say_hello"])
        client.runner(command, cwd=client.current_folder)
        self.assertEqual(['Hello Hello3', 'Hello Hello1', 'Hello Hello0'],
                         str(client.user_io.out).splitlines()[-3:])

        conan_info = ConanInfo.loads(load(os.path.join(client.current_folder, CONANINFO)))
        self.assertEqual("language=0\nstatic=True", conan_info.options.dumps())

        # Try to upload and reuse the binaries
        client.run("upload Hello1/0.1@lasote/stable --all")
        self.assertEqual(str(client.user_io.out).count("Uploading package"), 1)

        client2 = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})
        client2.save(files3)

        client2.run("install .")
        self.assertNotIn("Package installed in Hello0/0.1", client2.user_io.out)
        self.assertNotIn("Building", client2.user_io.out)
        client2.run("build .")

        self.assertNotIn("libhello0.a", client2.user_io.out)
        self.assertNotIn("libhello1.a", client2.user_io.out)
        self.assertNotIn("libhello3.a", client2.user_io.out)
        client2.runner(command, cwd=client2.current_folder)

        self.assertEqual(['Hello Hello3', 'Hello Hello1', 'Hello Hello0'],
                         str(client2.user_io.out).splitlines()[-3:])

        # Issue 79, fixing private deps from current project
        files3 = cpp_hello_conan_files("Hello3", "0.2", ["Hello1/0.1@lasote/stable",
                                                         ("Hello0/0.1@lasote/stable", "private")],
                                       language=1)

        client2.save(files3, clean_first=True)
        client2.run('install . -o language=1 --build missing')
        client2.run('build .')
        self.assertNotIn("libhello0.a", client2.user_io.out)
        self.assertNotIn("libhello1.a", client2.user_io.out)
        self.assertNotIn("libhello3.a", client2.user_io.out)
        client2.runner(command, cwd=client2.current_folder)
        self.assertEqual(['Hola Hello3', 'Hola Hello1',
                          'Hola Hello0', 'Hola Hello0'],
                         str(client2.user_io.out).splitlines()[-4:])
