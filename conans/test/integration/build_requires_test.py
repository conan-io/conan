import unittest
from nose_parameterized.parameterized import parameterized

from conans.test.utils.tools import TestClient
from conans.paths import CONANFILE


tool_conanfile = """
import os
from conans import ConanFile

class Tool(ConanFile):
    name = "Tool"
    version = "0.1"

    def package_info(self):
        self.env_info.TOOL_PATH.append("MyToolPath")
"""

tool_conanfile2 = tool_conanfile.replace("0.1", "0.3")

conanfile = """
import os
from conans import ConanFile, tools

class MyLib(ConanFile):
    name = "MyLib"
    version = "0.1"
    {}

    def build(self):
        self.output.info("ToolPath: %s" % os.getenv("TOOL_PATH"))
"""

requires = conanfile.format('build_requires = "Tool/0.1@lasote/stable"')
requires_range = conanfile.format('build_requires = "Tool/[>0.0]@lasote/stable"')
requirements = conanfile.format("""def build_requirements(self):
        self.build_requires("Tool/0.1@lasote/stable")""")
override = conanfile.format("""build_requires = "Tool/0.2@user/channel"

    def build_requirements(self):
        self.build_requires("Tool/0.1@lasote/stable")""")


profile = """
[build_requires]
Tool/0.3@lasote/stable
nonexistingpattern*: SomeTool/1.2@user/channel
"""


class BuildRequiresTest(unittest.TestCase):

    @parameterized.expand([(requires, ), (requires_range, ), (requirements, ), (override, )])
    def test_build_requires(self, conanfile):
        client = TestClient()
        client.save({CONANFILE: tool_conanfile}, clean_first=True)
        client.run("export lasote/stable")

        client.save({CONANFILE: conanfile}, clean_first=True)
        client.run("export lasote/stable")

        client.run("install MyLib/0.1@lasote/stable --build missing")
        self.assertIn("Tool/0.1@lasote/stable: Generating the package", client.user_io.out)
        self.assertIn("ToolPath: MyToolPath", client.user_io.out)

        client.run("install MyLib/0.1@lasote/stable")
        self.assertNotIn("Tool", client.user_io.out)
        self.assertIn("MyLib/0.1@lasote/stable: Already installed!", client.user_io.out)

    @parameterized.expand([(requires, ), (requires_range, ), (requirements, ), (override, )])
    def test_profile_override(self, conanfile):
        client = TestClient()
        client.save({CONANFILE: tool_conanfile2}, clean_first=True)
        client.run("export lasote/stable")

        client.save({CONANFILE: conanfile,
                     "profile.txt": profile,
                     "profile2.txt": profile.replace("0.3", "[>0.2]")}, clean_first=True)
        client.run("export lasote/stable")

        client.run("install MyLib/0.1@lasote/stable --profile ./profile.txt --build missing")
        self.assertNotIn("Tool/0.1", client.user_io.out)
        self.assertNotIn("Tool/0.2", client.user_io.out)
        self.assertIn("Tool/0.3@lasote/stable: Generating the package", client.user_io.out)
        self.assertIn("ToolPath: MyToolPath", client.user_io.out)

        client.run("install MyLib/0.1@lasote/stable")
        self.assertNotIn("Tool", client.user_io.out)
        self.assertIn("MyLib/0.1@lasote/stable: Already installed!", client.user_io.out)

        client.run("install MyLib/0.1@lasote/stable --profile ./profile2.txt --build")
        self.assertNotIn("Tool/0.1", client.user_io.out)
        self.assertNotIn("Tool/0.2", client.user_io.out)
        self.assertIn("Tool/0.3@lasote/stable: Generating the package", client.user_io.out)
        self.assertIn("ToolPath: MyToolPath", client.user_io.out)
