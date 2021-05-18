import os
import platform
import unittest

from conans.test.utils.tools import TestClient, GenConanfile
from conans.util.files import load


class VirtualEnvPythonGeneratorTest(unittest.TestCase):

    def test_no_value_declared(self):
        client = TestClient()
        dep1 = GenConanfile()

        base = '''
[requires]
base/0.1
[generators]
virtualenv
    '''
        client.save({"conanfile.py": dep1})
        client.run("create . base/0.1@")
        client.save({"conanfile.txt": base}, clean_first=True)
        client.run("install . -g virtualenv_python")
        name = "activate_run_python.sh" if platform.system() != "Windows" else "activate_run_python.bat"
        contents = client.load(name)
        self.assertNotIn("PYTHONPATH", contents)
