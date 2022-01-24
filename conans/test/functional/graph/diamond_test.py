import os
import platform
import unittest

import pytest

from conans.model.recipe_ref import RecipeReference
from conans.paths import CONANFILE
from conans.test.utils.tools import TestClient, TestServer
from conans.util.files import load


@pytest.mark.xfail(reason="cmake old generator will be removed")
@pytest.mark.slow
class DiamondTest(unittest.TestCase):

    def setUp(self):
        test_server = TestServer([],  # write permissions
                                 users={"lasote": "mypass"})  # exported users and passwords
        self.servers = {"default": test_server}

    def test_diamond_cmake(self):
        self.client = TestClient(servers=self.servers, inputs=["lasote", "mypass"])
        self._run(language=1)

    def test_diamond_cmake_targets(self):
        self.client = TestClient(servers=self.servers, inputs=["lasote", "mypass"])
        self._run(cmake_targets=True)

    def _export(self, name, version=None, deps=None, cmake_targets=False):
        files = cpp_hello_conan_files(name, version, deps, need_patch=True,
                                      cmake_targets=cmake_targets, with_exe=False)
        self.client.save(files, clean_first=True)
        self.client.run("export . --user=lasote --channel=stable")

    def _check_individual_deps(self):
        self.assertIn("INCLUDE [", self.client.out)
        output = str(self.client.out)
        latest_rrev = self.client.cache.get_latest_recipe_reference(RecipeReference.loads("hello0/0.1@lasote/stable"))
        ref_layout = self.client.cache.ref_layout(latest_rrev)
        self.assertIn(ref_layout.base_folder, output)
        cmakebuildinfo = load(os.path.join(self.client.current_folder, BUILD_INFO_CMAKE))
        self.assertIn("set(CONAN_LIBS helloHello3 helloHello1 helloHello2 hellohello0",
                      cmakebuildinfo)
        self.assertIn("set(CONAN_DEPENDENCIES Hello3 Hello1 Hello2 hello0)", cmakebuildinfo)
        build_file = os.path.join(self.client.current_folder, BUILD_INFO_CMAKE)
        content = load(build_file)
        for dep in ("Hello3", "Hello2", "hello1", "hello0"):
            self.assertIn("set(CONAN_INCLUDE_DIRS_%s " % dep.upper(), content)
            self.assertIn("set(CONAN_LIBS_%s hello%s)" % (dep.upper(), dep), content)

    def _run(self, cmake_targets=False, language=0):

        if platform.system() == "SunOS":
            return  # If is using sun-cc the gcc generator doesn't work

        self._export("hello0", "0.1", cmake_targets=cmake_targets)
        self._export("hello1", "0.1", ["hello0/0.1@lasote/stable"],
                     cmake_targets=cmake_targets)
        self._export("Hello2", "0.1", ["hello0/0.1@lasote/stable"],
                     cmake_targets=cmake_targets)
        self._export("Hello3", "0.1", ["hello1/0.1@lasote/stable", "hello2/0.1@lasote/stable"],
                     cmake_targets=cmake_targets)

        files3 = cpp_hello_conan_files("Hello4", "0.1", ["Hello3/0.1@lasote/stable"],
                                       language=language,
                                       cmake_targets=cmake_targets)

        # Add some stuff to base project conanfile to test further the individual
        # flags in build_info (txt, cmake) files
        content = files3[CONANFILE]
        content = content.replace("def build(self):",
                                  "def build(self):\n"
                                  "        self.output.info('INCLUDE %s' "
                                  "% list(self.deps_cpp_info['hello0'].include_paths))")
        files3[CONANFILE] = content
        self.client.save(files3)

        self.client.run("build . --build missing")
        if cmake_targets:
            self.assertIn("Conan: Using cmake targets configuration", self.client.out)
            self.assertNotIn("Conan: Using cmake global configuration", self.client.out)
        else:
            self.assertIn("Conan: Using cmake global configuration", self.client.out)
            self.assertNotIn("Conan: Using cmake targets configuration", self.client.out)
        self._check_individual_deps()

        def check_run_output(client):
            command = os.sep.join([".", "bin", "say_hello"])
            client.run_command(command)
            if language == 0:
                self.assertEqual(['Hello Hello4', 'Hello Hello3', 'Hello Hello1', 'Hello hello0',
                                  'Hello Hello2', 'Hello hello0'],
                                 str(client.out).splitlines()[-6:])
            else:
                self.assertEqual(['Hola Hello4', 'Hola Hello3', 'Hola Hello1', 'Hola hello0',
                                  'Hola Hello2', 'Hola hello0'],
                                 str(client.out).splitlines()[-6:])

        check_run_output(self.client)

        # Try to upload and reuse the binaries
        self.client.run("upload Hello* --confirm")
        self.assertEqual(str(self.client.out).count("Uploading package"), 4)

        # Reuse in another client
        client2 = TestClient(servers=self.servers, inputs=["lasote", "mypass"])
        client2.save(files3)
        client2.run("build .")

        self.assertNotIn("libhello0.a", client2.out)
        self.assertNotIn("libhello1.a", client2.out)
        self.assertNotIn("libhello2.a", client2.out)
        self.assertNotIn("libhello3.a", client2.out)
        check_run_output(client2)
