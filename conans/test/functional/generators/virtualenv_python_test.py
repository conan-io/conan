import platform
import unittest
import os

from conans.util.files import load

from conans.test.utils.tools import TestClient, GenConanfile


class VirtualEnvPythonGeneratorTest(unittest.TestCase):

    def simple_value_test(self):
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
        name = "activate_run_python.sh" if platform.system() != "Windows" else "activate_run_python.bat"
        contents = load(os.path.join(client.current_folder, name))
        self.assertNotIn("OTHER", contents)
        self.assertIn("PATH=", contents)
        self.assertIn("LD_LIBRARY_PATH=", contents)
        self.assertIn("DYLD_LIBRARY_PATH=", contents)

        if platform.system() != "Windows":

            self.assertIn('PYTHONPATH="/path/to/something"${PYTHONPATH+:$PYTHONPATH}', contents)
        else:
            self.assertIn('SET PYTHONPATH=/path/to/something;%PYTHONPATH%', contents)

    def multiple_value_test(self):
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
            name = "activate_run_python.sh" if platform.system() != "Windows" else "activate_run_python.bat"
            contents = load(os.path.join(client.current_folder, name))
            self.assertNotIn("OTHER", contents)
            if platform.system() != "Windows":
                self.assertIn('PYTHONPATH="/path/to/something":"/otherpath"'
                              '${PYTHONPATH+:$PYTHONPATH}', contents)
            else:
                self.assertIn('SET PYTHONPATH=/path/to/something;/otherpath;%PYTHONPATH%', contents)

    def no_value_declared_test(self):
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
        contents = load(os.path.join(client.current_folder, name))
        self.assertNotIn("PYTHONPATH", contents)
