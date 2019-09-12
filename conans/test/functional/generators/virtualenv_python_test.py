import platform
import unittest
import os

from conans.util.files import load

from conans.test.utils.tools import TestClient


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
        name = "activate_python.sh" if platform.system() != "Windows" else "activate_python.bat"
        contents = load(os.path.join(client.current_folder, name))
        self.assertNotIn("OTHER", contents)
        if platform.system != "Windows":
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
            name = "activate_python.sh" if platform.system() != "Windows" else "activate_python.bat"
            contents = load(os.path.join(client.current_folder, name))
            self.assertNotIn("OTHER", contents)
            if platform.system != "Windows":
                self.assertIn('PYTHONPATH="/path/to/something":"/otherpath"'
                              '${PYTHONPATH+:$PYTHONPATH}', contents)
            else:
                self.assertIn('SET PYTHONPATH=/path/to/something;%PYTHONPATH%', contents)
