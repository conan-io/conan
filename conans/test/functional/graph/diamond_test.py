import os
import platform
import unittest

import pytest

from conans.client.generators.text import TXTGenerator
from conans.paths import BUILD_INFO, BUILD_INFO_CMAKE, CONANFILE
from conans.test.assets.cpp_test_files import cpp_hello_conan_files
from conans.test.utils.tools import TestClient, TestServer
from conans.util.files import load


@pytest.mark.slow
class DiamondTest(unittest.TestCase):

    def setUp(self):
        test_server = TestServer([],  # write permissions
                                 users={"lasote": "mypass"})  # exported users and passwords
        self.servers = {"default": test_server}

    def test_diamond_cmake(self):
        self.client = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})
        self._run(use_cmake=True, language=1)

    def test_diamond_cmake_targets(self):
        self.client = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})
        self._run(use_cmake=True, cmake_targets=True)

    def test_diamond_default(self):
        self.client = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]},
                                 path_with_spaces=False)
        self._run(use_cmake=False)

    def _export(self, name, version=None, deps=None, use_cmake=True, cmake_targets=False):
        files = cpp_hello_conan_files(name, version, deps, need_patch=True, use_cmake=use_cmake,
                                      cmake_targets=cmake_targets, with_exe=False)
        self.client.save(files, clean_first=True)
        self.client.run("export . lasote/stable")

    def _check_individual_deps(self):
        self.assertIn("INCLUDE [", self.client.out)
        self.assertIn("/data/Hello0/0.1/lasote/stable", self.client.out)
        build_file = os.path.join(self.client.current_folder, BUILD_INFO)
        content = load(build_file)
        cmakebuildinfo = load(os.path.join(self.client.current_folder, BUILD_INFO_CMAKE))
        self.assertIn("set(CONAN_LIBS helloHello3 helloHello1 helloHello2 helloHello0",
                      cmakebuildinfo)
        self.assertIn("set(CONAN_DEPENDENCIES Hello3 Hello1 Hello2 Hello0)", cmakebuildinfo)
        deps_cpp_info, _, _, _ = TXTGenerator.loads(content)
        self.assertEqual(len(deps_cpp_info.include_paths), 4)
        for dep in ("Hello3", "Hello2", "Hello1", "Hello0"):
            self.assertEqual(len(deps_cpp_info[dep].include_paths), 1)
            self.assertEqual(len(deps_cpp_info[dep].lib_paths), 1)
            self.assertEqual(deps_cpp_info[dep].libs, ["hello%s" % dep])
        build_file = os.path.join(self.client.current_folder, BUILD_INFO_CMAKE)
        content = load(build_file)
        for dep in ("Hello3", "Hello2", "Hello1", "Hello0"):
            self.assertEqual(len(deps_cpp_info[dep].include_paths), 1)
            self.assertIn("set(CONAN_INCLUDE_DIRS_%s " % dep.upper(), content)
            self.assertIn("set(CONAN_LIBS_%s hello%s)" % (dep.upper(), dep), content)

    def _run(self, use_cmake=True, cmake_targets=False, language=0):

        if not use_cmake and platform.system() == "SunOS":
            return  # If is using sun-cc the gcc generator doesn't work

        self._export("Hello0", "0.1", use_cmake=use_cmake, cmake_targets=cmake_targets)
        self._export("Hello1", "0.1", ["Hello0/0.1@lasote/stable"], use_cmake=use_cmake,
                     cmake_targets=cmake_targets)
        self._export("Hello2", "0.1", ["Hello0/0.1@lasote/stable"], use_cmake=use_cmake,
                     cmake_targets=cmake_targets)
        self._export("Hello3", "0.1", ["Hello1/0.1@lasote/stable", "Hello2/0.1@lasote/stable"],
                     use_cmake=use_cmake, cmake_targets=cmake_targets)

        files3 = cpp_hello_conan_files("Hello4", "0.1", ["Hello3/0.1@lasote/stable"],
                                       language=language, use_cmake=use_cmake,
                                       cmake_targets=cmake_targets)

        # Add some stuff to base project conanfile to test further the individual
        # flags in build_info (txt, cmake) files
        content = files3[CONANFILE]
        content = content.replace("generators =", 'generators = "txt",')
        content = content.replace("def build(self):",
                                  "def build(self):\n"
                                  "        self.output.info('INCLUDE %s' "
                                  "% list(self.deps_cpp_info['Hello0'].include_paths))")
        files3[CONANFILE] = content
        self.client.save(files3)

        self.client.run("install . --build missing")
        if use_cmake:
            if cmake_targets:
                self.assertIn("Conan: Using cmake targets configuration", self.client.out)
                self.assertNotIn("Conan: Using cmake global configuration", self.client.out)
            else:
                self.assertIn("Conan: Using cmake global configuration", self.client.out)
                self.assertNotIn("Conan: Using cmake targets configuration", self.client.out)
        self.client.run("build .")
        self._check_individual_deps()

        def check_run_output(client):
            command = os.sep.join([".", "bin", "say_hello"])
            client.run_command(command)
            if language == 0:
                self.assertEqual(['Hello Hello4', 'Hello Hello3', 'Hello Hello1', 'Hello Hello0',
                                  'Hello Hello2', 'Hello Hello0'],
                                 str(client.out).splitlines()[-6:])
            else:
                self.assertEqual(['Hola Hello4', 'Hola Hello3', 'Hola Hello1', 'Hola Hello0',
                                  'Hola Hello2', 'Hola Hello0'],
                                 str(client.out).splitlines()[-6:])

        check_run_output(self.client)

        # Try to upload and reuse the binaries
        self.client.run("upload Hello* --all --confirm")
        self.assertEqual(str(self.client.out).count("Uploading package"), 4)

        # Reuse in another client
        client2 = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]},
                             path_with_spaces=use_cmake)
        files3[CONANFILE] = files3[CONANFILE].replace("generators =", 'generators = "txt",')
        client2.save(files3)
        client2.run("install .")
        client2.run("build .")

        self.assertNotIn("libhello0.a", client2.out)
        self.assertNotIn("libhello1.a", client2.out)
        self.assertNotIn("libhello2.a", client2.out)
        self.assertNotIn("libhello3.a", client2.out)
        check_run_output(client2)
