import os
import platform
import unittest


from conans.paths import CONANFILE
from conans.test.utils.tools import TestClient, GenConanfile


tool_conanfile = """
import os
from conans import ConanFile

class tool(ConanFile):
    name = "tool"
    version = "0.1"
    exports_sources = "mytool*"

    def package(self):
        self.copy("mytool*")

    def package_info(self):
        self.buildenv_info.append_path("PATH", self.package_folder)
"""

lib_conanfile = """
from conans import ConanFile

class mylib(ConanFile):
    name = "mylib"
    version = "0.1"

    def build(self):
        self.run("mytool")
"""

profile = """
[tool_requires]
tool/0.1@lasote/stable
nonexistingpattern*: sometool/1.2@user/channel
"""

profile2 = """
[tool_requires]
tool/0.1@lasote/stable
nonexistingpattern*: sometool/1.2@user/channel
"""


class BuildRequiresTest(unittest.TestCase):

    def _create(self, client):
        name = "mytool.bat" if platform.system() == "Windows" else "mytool"
        client.save({CONANFILE: tool_conanfile,
                     name: "echo Hello World!"}, clean_first=True)
        os.chmod(os.path.join(client.current_folder, name), 0o777)
        client.run("export . --user=lasote --channel=stable")

    def test_profile_requires(self):
        client = TestClient()
        self._create(client)

        client.save({CONANFILE: lib_conanfile,
                     "profile.txt": profile,
                     "profile2.txt": profile2}, clean_first=True)
        client.run("export . --user=lasote --channel=stable")

        client.run("install --reference=mylib/0.1@lasote/stable --profile ./profile.txt --build missing")
        self.assertIn("Hello World!", client.out)

        client.run("install --reference=mylib/0.1@lasote/stable --profile ./profile2.txt --build")
        self.assertIn("Hello World!", client.out)

    def test_profile_open_requires(self):
        client = TestClient()
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
        self.assertIn("ERROR: Missing prebuilt package for 'tool/0.1@lasote/stable'", client.out)
        client.run("install . --profile ./profile.txt --build=Pythontool", assert_error=True)
        self.assertIn("ERROR: Missing prebuilt package for 'tool/0.1@lasote/stable'", client.out)
        client.run("install . --profile ./profile.txt --build=*tool")
        self.assertIn("tool/0.1@lasote/stable: Generated conaninfo.txt", client.out)

        # now remove packages, ensure --build=missing also creates them
        client.run('remove "*" -p -f')
        client.run("install . --profile ./profile.txt --build=missing")
        self.assertIn("tool/0.1@lasote/stable: Generated conaninfo.txt", client.out)

    def test_profile_test_requires(self):
        client = TestClient()
        self._create(client)

        test_conanfile = """
import os
from conans import ConanFile, tools

class Testmylib(ConanFile):
    def requirements(self):
        self.requires(self.tested_reference_str)

    def build(self):
        self.run("mytool")

    def test(self):
        pass
        """
        client.save({CONANFILE: lib_conanfile,
                     "test_package/conanfile.py": test_conanfile,
                     "profile.txt": profile,
                     "profile2.txt": profile2}, clean_first=True)

        client.run("create . --user=lasote --channel=stable --profile ./profile.txt --build missing")
        self.assertEqual(2, str(client.out).splitlines().count("Hello World!"))

    def test_consumer_patterns(self):
        client = TestClient()
        self._create(client)

        test_conanfile = """
import os
from conans import ConanFile, tools

class Testmylib(ConanFile):

    def build(self):
        self.run("mytool")
    def test(self):
        pass
        """
        lib_conanfile = """
import os
from conans import ConanFile, tools

class mylib(ConanFile):
    name = "mylib"
    version = "0.1"


"""
        profile_patterns = """
[tool_requires]
&: tool/0.1@lasote/stable
nonexistingpattern*: sometool/1.2@user/channel
"""
        client.save({CONANFILE: lib_conanfile,
                     "test_package/conanfile.py": test_conanfile,
                     "profile.txt": profile_patterns}, clean_first=True)

        client.run("create . --user=lasote --channel=stable --profile=./profile.txt --build=missing")
        self.assertEqual(1, str(client.out).splitlines().count("Hello World!"))

    def test_build_requires_options(self):
        client = TestClient()
        client.save({CONANFILE: GenConanfile("mytool", "0.1")})
        client.run("export . --user=lasote --channel=stable")

        conanfile = """
from conans import ConanFile, tools

class mylib(ConanFile):
    name = "mylib"
    version = "0.1"
    build_requires = "mytool/0.1@lasote/stable"
    options = {"coverage": [True, False]}
    def build(self):
        self.output.info("Coverage %s" % self.options.coverage)
"""
        client.save({CONANFILE: conanfile}, clean_first=True)
        client.run("build . -o mylib:coverage=True --build missing")
        self.assertIn("mytool/0.1@lasote/stable from local cache", client.out)
        self.assertIn("mytool/0.1@lasote/stable: Calling build()", client.out)
        self.assertIn("conanfile.py (mylib/0.1): Coverage True", client.out)

        client.save({CONANFILE: conanfile}, clean_first=True)
        client.run("build . -o coverage=True")
        self.assertIn("mytool/0.1@lasote/stable from local cache", client.out)
        self.assertIn("mytool/0.1@lasote/stable: Already installed!", client.out)
        self.assertIn("conanfile.py (mylib/0.1): Coverage True", client.out)
