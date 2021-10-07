import os
import platform
import unittest

from conans.test.utils.tools import TestClient, GenConanfile
from conans.util.files import load


class VirtualEnvPythonGeneratorTest(unittest.TestCase):

    def test_simple_value(self):
        client = TestClient()
        dep1 = """
import os
from conans import ConanFile

class BaseConan(ConanFile):
    name = "base"
    version = "0.1"

    def package_info(self):
        self.env_info.PYTHONPATH="/path/to/something"
        self.env_info.LD_LIBRARY_PATH="/path/ld_library"
        self.env_info.DYLD_LIBRARY_PATH="/path/dyld_library"
        self.env_info.PATH="/path/path"
        self.env_info.OTHER="23"
"""

        base = '''
[requires]
base/0.1
[generators]
virtualenv
    '''
        client.save({"conanfile.py": dep1})
        client.run("create . ")
        client.save({"conanfile.txt": base}, clean_first=True)
        client.run("install . -g virtualenv_python")

        if platform.system() != "Windows":
            contents = client.load("environment_run_python.sh.env")
            self.assertIn('PYTHONPATH="/path/to/something"${PYTHONPATH:+:$PYTHONPATH}', contents)
        else:
            contents = client.load("environment_run_python.bat.env")
            self.assertIn('PYTHONPATH=/path/to/something;%PYTHONPATH%', contents)
        self.assertNotIn("OTHER", contents)
        self.assertIn("PATH=", contents)
        self.assertIn("LD_LIBRARY_PATH=", contents)
        self.assertIn("DYLD_LIBRARY_PATH=", contents)

    def test_multiple_value(self):
            client = TestClient()
            dep1 = """
from conans import ConanFile

class BaseConan(ConanFile):
    name = "base"
    version = "0.1"

    def package_info(self):
        self.env_info.PYTHONPATH=["/path/to/something", "/otherpath"]
        self.env_info.OTHER="23"
"""

            base = '''
    [requires]
    base/0.1
    [generators]
    virtualenv
        '''
            client.save({"conanfile.py": dep1})
            client.run("create . ")
            client.save({"conanfile.txt": base}, clean_first=True)
            client.run("install . -g virtualenv_python")

            if platform.system() != "Windows":
                contents = client.load("environment_run_python.sh.env")
                self.assertIn('PYTHONPATH="/path/to/something":"/otherpath"'
                              '${PYTHONPATH:+:$PYTHONPATH}', contents)
            else:
                contents = client.load("environment_run_python.bat.env")
                self.assertIn('PYTHONPATH=/path/to/something;/otherpath;%PYTHONPATH%', contents)
            self.assertNotIn("OTHER", contents)

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
