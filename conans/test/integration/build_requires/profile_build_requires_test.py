import os
import platform
import unittest

from conans.paths import CONANFILE
from conans.test.utils.tools import TestClient, GenConanfile
from conans.util.files import save

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
        self.buildenv_info.append_path("PATH", self.package_folder)
"""

lib_conanfile = """
from conans import ConanFile

class MyLib(ConanFile):
    name = "MyLib"
    version = "0.1"

    def build(self):
        self.run("mytool")
"""

profile = """
[build_requires]
Tool/0.1@lasote/stable
nonexistingpattern*: SomeTool/1.2@user/channel
"""

profile2 = """
[build_requires]
Tool/0.1@lasote/stable
nonexistingpattern*: SomeTool/1.2@user/channel
"""


class BuildRequiresTest(unittest.TestCase):

    def _create(self, client):
        name = "mytool.bat" if platform.system() == "Windows" else "mytool"
        client.save({CONANFILE: tool_conanfile,
                     name: "echo Hello World!"}, clean_first=True)
        os.chmod(os.path.join(client.current_folder, name), 0o777)
        client.run("export . lasote/stable")

    def test_profile_requires(self):
        client = TestClient()
        save(client.cache.new_config_path, "tools.env.virtualenv:auto_use=True")
        self._create(client)

        client.save({CONANFILE: lib_conanfile,
                     "profile.txt": profile,
                     "profile2.txt": profile2}, clean_first=True)
        client.run("export . lasote/stable")

        client.run("install MyLib/0.1@lasote/stable --profile ./profile.txt --build missing")
        self.assertIn("Hello World!", client.out)

        client.run("install MyLib/0.1@lasote/stable --profile ./profile2.txt --build")
        self.assertIn("Hello World!", client.out)

    def test_profile_open_requires(self):
        client = TestClient()
        save(client.cache.new_config_path, "tools.env.virtualenv:auto_use=True")
        self._create(client)

        client.save({CONANFILE: lib_conanfile,
                     "profile.txt": profile}, clean_first=True)

        client.run("build . --profile ./profile.txt --build missing")
        self.assertIn("Hello World!", client.out)

    def test_build_mode_requires(self):
        client = TestClient()
        self._create(client)

        client.save({CONANFILE: lib_conanfile,
                     "profile.txt": profile}, clean_first=True)

        client.run("install . --profile ./profile.txt", assert_error=True)
        self.assertIn("ERROR: Missing prebuilt package for 'Tool/0.1@lasote/stable'", client.out)
        client.run("install . --profile ./profile.txt --build=PythonTool", assert_error=True)
        self.assertIn("ERROR: Missing prebuilt package for 'Tool/0.1@lasote/stable'", client.out)
        client.run("install . --profile ./profile.txt --build=*Tool")
        self.assertIn("Tool/0.1@lasote/stable: Generated conaninfo.txt", client.out)

        # now remove packages, ensure --build=missing also creates them
        client.run('remove "*" -p -f')
        client.run("install . --profile ./profile.txt --build=missing")
        self.assertIn("Tool/0.1@lasote/stable: Generated conaninfo.txt", client.out)

    def test_profile_test_requires(self):
        client = TestClient()
        save(client.cache.new_config_path, "tools.env.virtualenv:auto_use=True")
        self._create(client)

        test_conanfile = """
import os
from conans import ConanFile, tools

class TestMyLib(ConanFile):

    def build(self):
        self.run("mytool")

    def test(self):
        pass
        """
        client.save({CONANFILE: lib_conanfile,
                     "test_package/conanfile.py": test_conanfile,
                     "profile.txt": profile,
                     "profile2.txt": profile2}, clean_first=True)

        client.run("create . lasote/stable --profile ./profile.txt --build missing")
        self.assertEqual(2, str(client.out).splitlines().count("Hello World!"))

    def test_consumer_patterns(self):
        client = TestClient()
        save(client.cache.new_config_path, "tools.env.virtualenv:auto_use=True")
        self._create(client)

        test_conanfile = """
import os
from conans import ConanFile, tools

class TestMyLib(ConanFile):

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


"""
        profile_patterns = """
[build_requires]
&: Tool/0.1@lasote/stable
nonexistingpattern*: SomeTool/1.2@user/channel
"""
        client.save({CONANFILE: lib_conanfile,
                     "test_package/conanfile.py": test_conanfile,
                     "profile.txt": profile_patterns}, clean_first=True)

        client.run("create . lasote/stable --profile=./profile.txt --build=missing")
        self.assertEqual(1, str(client.out).splitlines().count("Hello World!"))

    def test_build_requires_options(self):
        client = TestClient()
        client.save({CONANFILE: GenConanfile("MyTool", "0.1")})
        client.run("export . lasote/stable")

        conanfile = """
from conans import ConanFile, tools

class MyLib(ConanFile):
    name = "MyLib"
    version = "0.1"
    build_requires = "MyTool/0.1@lasote/stable"
    options = {"coverage": [True, False]}
    def build(self):
        self.output.info("Coverage %s" % self.options.coverage)
"""
        client.save({CONANFILE: conanfile}, clean_first=True)
        client.run("build . -o MyLib:coverage=True --build missing")
        self.assertIn("MyTool/0.1@lasote/stable from local cache", client.out)
        self.assertIn("MyTool/0.1@lasote/stable: Calling build()", client.out)
        self.assertIn("conanfile.py (MyLib/0.1): Coverage True", client.out)

        client.save({CONANFILE: conanfile}, clean_first=True)
        client.run("build . -o coverage=True")
        self.assertIn("MyTool/0.1@lasote/stable from local cache", client.out)
        self.assertIn("MyTool/0.1@lasote/stable: Already installed!", client.out)
        self.assertIn("conanfile.py (MyLib/0.1): Coverage True", client.out)
