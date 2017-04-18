import unittest
import platform
import os

from conans.test.utils.tools import TestClient
from conans.paths import CONANFILE


tool_conanfile = """
import os
from conans import ConanFile

class Tool(ConanFile):
    name = "Tool"
    version = "0.1"
    exports_sources = "mytool*"

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
nonexistingpattern*: SomeTool/1.2@user/channel
"""

profile2 = """
[build_requires]
Tool/0.1@lasote/stable
PythonTool/0.1@lasote/stable
nonexistingpattern*: SomeTool/1.2@user/channel
"""


class BuildRequiresTest(unittest.TestCase):

    def _create(self, client):
        name = "mytool.bat" if platform.system() == "Windows" else "mytool"
        client.save({CONANFILE: tool_conanfile,
                     name: "echo Hello World!"}, clean_first=True)
        os.chmod(os.path.join(client.current_folder, name), 0o777)
        client.run("export lasote/stable")
        client.save({CONANFILE: python_conanfile,
                     "mypythontool.py": """def tool_hello_world():
    return 'Hello world from python tool!'"""}, clean_first=True)
        client.run("export lasote/stable")

    def test_profile_requires(self):
        client = TestClient()
        self._create(client)

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

    def test_profile_open_requires(self):
        client = TestClient()
        self._create(client)

        client.save({CONANFILE: lib_conanfile,
                     "profile.txt": profile}, clean_first=True)

        client.run("install --profile ./profile.txt --build missing")
        self.assertNotIn("Hello World!", client.user_io.out)
        client.run("build")
        self.assertIn("Hello World!", client.user_io.out)
        self.assertIn("Project: Hello world from python tool!", client.user_io.out)

    def test_build_mode_requires(self):
        client = TestClient()
        self._create(client)

        client.save({CONANFILE: lib_conanfile,
                     "profile.txt": profile}, clean_first=True)

        error = client.run("install --profile ./profile.txt", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: Missing prebuilt package for 'PythonTool/0.1@lasote/stable'",
                      client.user_io.out)
        error = client.run("install --profile ./profile.txt --build=PythonTool",
                           ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: Missing prebuilt package for 'Tool/0.1@lasote/stable'",
                      client.user_io.out)
        client.run("install --profile ./profile.txt --build=*Tool")
        self.assertIn("Installed build requires: [Tool/0.1@lasote/stable, "
                      "PythonTool/0.1@lasote/stable]", client.user_io.out)
        self.assertIn("Tool/0.1@lasote/stable: Generated conaninfo.txt", client.user_io.out)
        self.assertIn("PythonTool/0.1@lasote/stable: Generated conaninfo.txt", client.user_io.out)

        # now remove packages, ensure --build=missing also creates them
        client.run('remove "*" -p -f')
        client.run("install --profile ./profile.txt --build=missing")
        self.assertIn("Installed build requires: [Tool/0.1@lasote/stable, "
                      "PythonTool/0.1@lasote/stable]", client.user_io.out)
        self.assertIn("Tool/0.1@lasote/stable: Generated conaninfo.txt", client.user_io.out)
        self.assertIn("PythonTool/0.1@lasote/stable: Generated conaninfo.txt", client.user_io.out)

    def test_profile_test_requires(self):
        client = TestClient()
        self._create(client)

        test_conanfile = """
import os
from conans import ConanFile, tools

class TestMyLib(ConanFile):
    requires = "MyLib/0.1@lasote/stable"

    def build(self):
        self.run("mytool")
        with tools.pythonpath(self):
            import mypythontool
            self.output.info(mypythontool.tool_hello_world())
    def test(self):
        pass
        """
        client.save({CONANFILE: lib_conanfile,
                     "test_package/conanfile.py": test_conanfile,
                     "profile.txt": profile,
                     "profile2.txt": profile2}, clean_first=True)

        client.run("test_package --profile ./profile.txt --build missing")
        self.assertEqual(2, str(client.user_io.out).splitlines().count("Hello World!"))
        self.assertIn("MyLib/0.1@lasote/stable: Hello world from python tool!", client.user_io.out)
        self.assertIn("Project: Hello world from python tool!", client.user_io.out)

    def test_consumer_patterns(self):
        client = TestClient()
        self._create(client)

        test_conanfile = """
import os
from conans import ConanFile, tools

class TestMyLib(ConanFile):
    requires = "MyLib/0.1@lasote/stable"

    def build(self):
        self.run("mytool")
    def test(self):
        pass
        """
        lib_conanfile = """
import os
from conans import ConanFile, tools

class MyLib(ConanFile):
    name = "MyLib"
    version = "0.1"

    def build(self):
        with tools.pythonpath(self):
            import mypythontool
            self.output.info(mypythontool.tool_hello_world())
"""
        profile_patterns = """
[build_requires]
&: Tool/0.1@lasote/stable
&!: PythonTool/0.1@lasote/stable
nonexistingpattern*: SomeTool/1.2@user/channel
"""
        client.save({CONANFILE: lib_conanfile,
                     "test_package/conanfile.py": test_conanfile,
                     "profile.txt": profile_patterns}, clean_first=True)

        client.run("test_package --profile ./profile.txt --build missing")
        self.assertEqual(1, str(client.user_io.out).splitlines().count("Hello World!"))
        self.assertIn("MyLib/0.1@lasote/stable: Hello world from python tool!", client.user_io.out)
        self.assertNotIn("Project: Hello world from python tool!", client.user_io.out)
