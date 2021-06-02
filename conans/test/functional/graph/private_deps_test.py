import os
import re
import unittest

import pytest

from conans.model.info import ConanInfo
from conans.model.ref import ConanFileReference
from conans.paths import BUILD_INFO_CMAKE, CONANINFO
from conans.test.assets.cpp_test_files import cpp_hello_conan_files
from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestClient, TestServer, GenConanfile
from conans.util.files import load


@pytest.mark.slow
@pytest.mark.tool_cmake
class PrivateDepsTest(unittest.TestCase):

    def setUp(self):
        test_server = TestServer()
        self.servers = {"default": test_server}
        self.client = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})

    def _export_upload(self, name=0, version=None, deps=None, msg=None, static=True, build=True,
                       upload=True):
        files = cpp_hello_conan_files(name, version, deps, msg=msg, static=static,
                                      private_includes=True, build=build,
                                      cmake_targets=False)
        ref = ConanFileReference(name, version, "lasote", "stable")
        self.client.save(files, clean_first=True)
        self.client.run("export . lasote/stable")
        if upload:
            self.client.run("upload %s" % str(ref))

    def _export(self, name=0, version=None, deps=None):
        files = cpp_hello_conan_files(name, version, deps,
                                      private_includes=True, build=False,
                                      cmake_targets=True)
        self.client.save(files, clean_first=True)
        self.client.run("export . lasote/stable")

    def test_modern_cmake(self):
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

    def test_consumer_force_build(self):
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
        # self.assertNotIn("Hello0/0.1@lasote/stable", self.client.out)
        self.assertNotIn("Hello0/0.1@lasote/stable: Package installed", self.client.out)

        # Remove local recipes and packages
        self.client.run('remove Hello* -f')

        # Install them without force build, private is not retrieved
        self.client.run('install Hello1/0.1@lasote/stable ')
        self.assertNotIn("Hello0/0.1@lasote/stable: Package installed", self.client.out)

        # Remove local recipes and packages
        self.client.run('remove Hello* -f')

        # Install them without forcing build
        self.client.run('install Hello1/0.1@lasote/stable --build Hello1')
        self.assertIn("Hello0/0.1@lasote/stable: Package installed", self.client.out)
        self.assertIn("Hello1/0.1@lasote/stable: Building your package", self.client.out)

    def test_consumer_private(self):
        self._export_upload("Hello0", "0.1", build=False, upload=False)
        self._export_upload("Hello1", "0.1", deps=["Hello0/0.1@lasote/stable"],
                            build=False, upload=False)
        self._export_upload("Hello2", "0.1", deps=[("Hello1/0.1@lasote/stable", "private")],
                            build=False, upload=False)
        self._export_upload("Hello3", "0.1", deps=[("Hello2/0.1@lasote/stable"),
                                                   ],
                            build=False, upload=False)

        self.client.run('install . --build missing')
        self.assertIn("Hello0/0.1@lasote/stable: Generating the package", self.client.out)
        self.assertIn("Hello1/0.1@lasote/stable: Generating the package", self.client.out)
        self.assertIn("Hello2/0.1@lasote/stable: Generating the package", self.client.out)

        self.client.run("remove Hello0* -p -f ")
        self.client.run("remove Hello1* -p -f")
        self.client.run("search Hello0/0.1@lasote/stable")
        self.assertIn("There are no packages for reference 'Hello0/0.1@lasote/stable', but package recipe found.",
                      self.client.out)
        self.client.run("search Hello1/0.1@lasote/stable")
        self.assertIn("There are no packages for reference 'Hello1/0.1@lasote/stable', but package recipe found.",
                      self.client.out)

        self.client.run('install . --build missing')
        self.assertNotIn("Hello0/0.1@lasote/stable: Generating the package",
                         self.client.out)
        self.assertNotIn("Hello1/0.1@lasote/stable: Generating the package",
                         self.client.out)
