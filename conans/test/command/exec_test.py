import unittest
import os
from conans.test.utils.tools import TestClient
from conans.tools import os_info

class ExecTest(unittest.TestCase):

    def _true_cmd(self):
        if os_info.is_windows and not os_info.is_posix:
            return "cmd /C EXIT"
        return "true"

    def _false_cmd(self):
        if os_info.is_windows and not os_info.is_posix:
            return "cmd /C EXIT 1"
        return "false"

    def _env_cmd(self):
        if os_info.is_windows and not os_info.is_posix:
            return "cmd /C SET"
        return "env"

    def _setup_recipes(self, client):
        toolA = """
import os
from conans import ConanFile

class ToolAConan(ConanFile):
    name = "toola"
    version = "0.1"

    def package_info(self):
        self.env_info.PATH = [os.path.join("toola","bin")]
"""

        toolB = """
import os
from conans import ConanFile

class ToolBConan(ConanFile):
    name = "toolb"
    version = "0.1"
    requires = "toola/0.1@lasote/testing"

    def package_info(self):
        self.env_info.PATH = [os.path.join("toolb","bin")]
"""

        client.save({"conanfile.py": toolA})
        client.run("create . lasote/testing")
        client.save({"conanfile.py": toolB}, clean_first=True)
        client.run("export . lasote/testing")

    def true_test(self):
        client = TestClient()
        client.run_in_external_process("exec %s" % self._true_cmd())

    def false_test(self):
        client = TestClient()
        self.assertEqual(1,client.run_in_external_process("exec %s" % self._false_cmd(),
                                                            ignore_error=True))

    def env_test(self):
        client = TestClient()
        client.run_in_external_process("exec -e FOOKEY=FOOVALUE %s" % self._env_cmd())
        self.assertIn("FOOKEY=FOOVALUE", client.out)

    def conan_output_test(self):
        client = TestClient()
        self._setup_recipes(client)
        client.run_in_external_process("exec -ref toola/0.1@lasote/testing %s" % self._true_cmd())
        self.assertIn("Requirements", client.out)
        self.assertIn("toola/0.1@lasote/testing from local cache", client.out)
        self.assertNotIn("toolb/0.1@lasote/testing", client.out)

    def quiet_test(self):
        client = TestClient()
        self._setup_recipes(client)
        client.run_in_external_process("exec -q -ref toola/0.1@lasote/testing %s" % self._true_cmd())
        self.assertNotIn("Requirements", client.out)
        self.assertNotIn("toola/0.1@lasote/testing", client.out)
        self.assertNotIn("toolb/0.1@lasote/testing", client.out)

    def toolA_test(self):
        client = TestClient()
        self._setup_recipes(client)
        client.run_in_external_process("exec -ref toola/0.1@lasote/testing %s" % self._env_cmd())
        self.assertIn("PATH=%s%s%s" % (os.path.join("toola","bin"), os.pathsep, os.environ["PATH"]), client.out)

    def toolB_unbuild_test(self):
        client = TestClient()
        self._setup_recipes(client)
        self.assertEqual(1,client.run_in_external_process("exec -ref toolb/0.1@lasote/testing %s" % self._env_cmd(),
                                                            ignore_error=True))

    def toolB_build_test(self):
        client = TestClient()
        self._setup_recipes(client)
        client.run_in_external_process("exec --build=missing -ref toolb/0.1@lasote/testing %s" % self._env_cmd())
        self.assertIn("PATH=%s%s%s%s%s" % (os.path.join("toolb","bin"), os.pathsep,
                                           os.path.join("toola","bin"), os.pathsep,
                                           os.environ["PATH"]), client.out)

    def path_and_references_test(self):
        client = TestClient()
        self.assertEqual(1,client.run_in_external_process("exec --path . -ref toola/0.1@lasote/testing %s" % self._env_cmd(),
                                                            ignore_error=True))
        self.assertIn("ERROR: Specifying references and a recipe path at the same time is not supported.", client.out)

    def path_directory_test(self):
        client = TestClient()
        self._setup_recipes(client)
        client.run_in_external_process("exec --path . %s" % self._env_cmd())
        self.assertIn("PATH=%s%s%s" % (os.path.join("toola","bin"), os.pathsep, os.environ["PATH"]), client.out)

    def path_recipe_test(self):
        conanfile = '''
[requires]
toolb/0.1@lasote/testing
    '''
        client = TestClient()
        self._setup_recipes(client)
        client.save({"conanfile.txt": conanfile}, clean_first=True)
        client.run_in_external_process("exec --build=toolb --path conanfile.txt %s" % self._env_cmd())

        self.assertIn("PROJECT: Installing %s" % os.path.join(client.current_folder, "conanfile.txt"), client.out)
        self.assertIn("toola/0.1@lasote/testing from local cache", client.out)
        self.assertIn("toolb/0.1@lasote/testing from local cache", client.out)
        self.assertIn("PATH=%s%s%s%s%s" % (os.path.join("toolb","bin"), os.pathsep,
                                           os.path.join("toola","bin"), os.pathsep,
                                           os.environ["PATH"]), client.out)
