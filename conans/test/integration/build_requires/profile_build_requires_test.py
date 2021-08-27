import os
import platform
import unittest

import pytest

from conans.paths import CONANFILE
from conans.test.utils.tools import TestClient, GenConanfile

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
        self.buildenv_info.append_path("PATH", self.package_folder)
"""

lib_conanfile = """
import os
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

    def test_duplicated_build_requires(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . build_require/0.1@user/testing")
        client.run("export . MyLib/0.1@user/testing")

        client.save({"conanfile.py": GenConanfile().with_requires("MyLib/0.1@user/testing"),
                     "test_package/conanfile.py": GenConanfile().with_test("pass"),
                     "myprofile": "[build_requires]\nbuild_require/0.1@user/testing"})
        client.run("create . Pkg/0.1@user/testing -pr=myprofile --build=missing")
        self.assertEqual(1, str(client.out).count("build_require/0.1@user/testing "
                                                  "from local cache"))
        self.assertIn("build_require/0.1@user/testing: Already installed!", client.out)
        self.assertIn("Pkg/0.1@user/testing (test package): Applying build-requirement: "
                      "build_require/0.1@user/testing", client.out)
        self.assertIn("Pkg/0.1@user/testing: Applying build-requirement: "
                      "build_require/0.1@user/testing", client.out)
        self.assertIn("MyLib/0.1@user/testing: Applying build-requirement: "
                      "build_require/0.1@user/testing", client.out)

    def test_recursive_build_requires(self):
        client = TestClient()
        profile = """[build_requires]
build1/0.1@user/testing
build2/0.1@user/testing
"""
        client.save({"conanfile.py": GenConanfile(),
                     "myprofile": profile})
        client.run("create . build1/0.1@user/testing")
        client.run("create . build2/0.1@user/testing")

        client.run("create . MyLib/0.1@user/testing -pr=myprofile --build")
        self.assertEqual(2, str(client.out).count("Applying build-requirement"))
        self.assertEqual(1, str(client.out).count(
            "MyLib/0.1@user/testing: Applying build-requirement: build1/0.1@user/testing"))
        self.assertEqual(1, str(client.out).count(
            "MyLib/0.1@user/testing: Applying build-requirement: build2/0.1@user/testing"))

        client.run("info MyLib/0.1@user/testing -pr=myprofile --dry-build")
        # Only 1 node has build requires
        self.assertEqual(1, str(client.out).count("Build Requires"))

    def _create(self, client):
        name = "mytool.bat" if platform.system() == "Windows" else "mytool"
        client.save({CONANFILE: tool_conanfile,
                     name: "echo Hello World!"}, clean_first=True)
        os.chmod(os.path.join(client.current_folder, name), 0o777)
        client.run("export . lasote/stable")

    def test_profile_requires(self):
        client = TestClient()
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
        self._create(client)

        client.save({CONANFILE: lib_conanfile,
                     "profile.txt": profile}, clean_first=True)

        client.run("build . --profile ./profile.txt --build missing")
        self.assertIn("Hello World!", client.out)

    @pytest.mark.xfail(reason="cache2.0 revisit the test")
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
        client.save({CONANFILE: lib_conanfile,
                     "test_package/conanfile.py": test_conanfile,
                     "profile.txt": profile,
                     "profile2.txt": profile2}, clean_first=True)

        client.run("create . lasote/stable --profile ./profile.txt --build missing")
        self.assertEqual(2, str(client.out).splitlines().count("Hello World!"))

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
