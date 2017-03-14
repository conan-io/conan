import unittest
from conans.test.utils.tools import TestClient
from conans.test.utils.python_test_files import py_hello_conan_files
import platform


class PythonDiamondTest(unittest.TestCase):

    def setUp(self):
        self.client = TestClient()

    def _export_upload(self, name, version=None, deps=None):
        files = py_hello_conan_files(name, version, deps)
        self.client.save(files, clean_first=True)
        self.client.run("export lasote/stable")

    def reuse_test(self):
        self._export_upload("Hello0", "0.1")
        self._export_upload("Hello1", "0.1", ["Hello0/0.1@lasote/stable"])
        self._export_upload("Hello2", "0.1", ["Hello0/0.1@lasote/stable"])
        self._export_upload("Hello3", "0.1", ["Hello1/0.1@lasote/stable",
                                              "Hello2/0.1@lasote/stable"])

        files3 = py_hello_conan_files("Hello4", "0.1", ["Hello3/0.1@lasote/stable"])
        self.client.save(files3, clean_first=True)

        self.client.run("install .")
        self.assertIn("Hello1/0.1@lasote/stable: Build stuff Hello0", self.client.user_io.out)
        self.assertIn("Hello2/0.1@lasote/stable: Build stuff Hello0", self.client.user_io.out)

        self.assertIn(" ".join(["Hello3/0.1@lasote/stable: Build stuff Hello1",
                                "Hello3/0.1@lasote/stable: Build stuff Hello0",
                                "Hello3/0.1@lasote/stable: Build stuff Hello2",
                                "Hello3/0.1@lasote/stable: Build stuff Hello0"]),
                      " ".join(str(self.client.user_io.out).splitlines()))
        self.assertNotIn("Project: Build stuff Hello3", self.client.user_io.out)

        self.client.run("build")
        self.assertIn("Project: Build stuff Hello3", self.client.user_io.out)

        if platform.system() == "Windows":
            command = "activate && python main.py"
        else:
            command = 'bash -c "source activate.sh && python main.py"'
        self.client.runner(command, cwd=self.client.current_folder)
        self.assertEqual(['Hello Hello4', 'Hello Hello3', 'Hello Hello1', 'Hello Hello0',
                          'Hello Hello2', 'Hello Hello0'],
                         str(self.client.user_io.out).splitlines()[-6:])
