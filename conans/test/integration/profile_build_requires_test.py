import unittest

from conans.test.utils.tools import TestClient
from conans.paths import CONANFILE


tool_conanfile = """
import os
from conans import ConanFile

class Tool(ConanFile):
    name = "Tool"
    version = "0.1"
    exports_sources = "mytool*"
    build_policy = "missing"

    def package(self):
        self.copy("mytool*")

    def package_info(self):
        self.env_info.PATH.append(self.package_folder)
"""

python_conanfile = """
import os
from conans import ConanFile

class Tool(ConanFile):
    name = "PythonTool"
    version = "0.1"
    exports_sources = "mypythontool.py"
    build_policy = "missing"

    def package(self):
        self.copy("mypythontool.py")

    def package_info(self):
        self.env_info.PYTHONPATH.append(self.package_folder)

"""


lib_conanfile = """
import os
from conans import ConanFile, tools

class MyLib(ConanFile):
    name = "MyLib"
    version = "0.1"

    def build(self):
        self.run("mytool")
        with tools.pythonpath(self):
            import mypythontool
            self.output.info(mypythontool.tool_hello_world())
"""

profile = """
[build_requires]
Tool/0.1@lasote/stable, PythonTool/0.1@lasote/stable
"""

profile2 = """
[build_requires]
Tool/0.1@lasote/stable
PythonTool/0.1@lasote/stable
"""


class BuildRequiresTest(unittest.TestCase):

    def test_profile_requires(self):
        client = TestClient()
        client.save({CONANFILE: tool_conanfile,
                     "mytool.bat": "echo Hello World!"}, clean_first=True)
        client.run("export lasote/stable")
        client.save({CONANFILE: python_conanfile,
                     "mypythontool.py": """def tool_hello_world():
    return 'Hello world from python tool!'"""}, clean_first=True)
        client.run("export lasote/stable")

        client.save({CONANFILE: lib_conanfile,
                     "profile.txt": profile,
                     "profile2.txt": profile2}, clean_first=True)
        client.run("export lasote/stable")

        client.run("install MyLib/0.1@lasote/stable --profile ./profile.txt --build missing")
        self.assertIn("Hello World!", client.user_io.out)
        self.assertIn("MyLib/0.1@lasote/stable: Hello world from python tool!", client.user_io.out)

        client.run("install MyLib/0.1@lasote/stable --profile ./profile2.txt --build")
        self.assertIn("Hello World!", client.user_io.out)
        self.assertIn("MyLib/0.1@lasote/stable: Hello world from python tool!", client.user_io.out)
