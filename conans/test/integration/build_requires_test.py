import unittest
from parameterized.parameterized import parameterized

from conans.test.utils.tools import TestClient
from conans.paths import CONANFILE
import os
from conans.util.files import load


tool_conanfile = """from conans import ConanFile

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

    def test_dependents_txt(self):
        client = TestClient()
        boost = """from conans import ConanFile
class Boost(ConanFile):
    def package_info(self):
        self.env_info.PATH.append("myboostpath")
"""
        client.save({CONANFILE: boost})
        client.run("create . Boost/1.0@user/channel")
        other = """[build_requires]
Boost/1.0@user/channel
"""
        client.save({"conanfile.txt": other}, clean_first=True)
        client.run("install .")

        self.assertIn("""Build requirements
    Boost/1.0@user/channel""", client.out)
        conanbuildinfo = load(os.path.join(client.current_folder, "conanbuildinfo.txt"))
        self.assertIn('PATH=["myboostpath"]', conanbuildinfo)

    def test_dependents(self):
        client = TestClient()
        boost = """from conans import ConanFile
class Boost(ConanFile):
    def package_info(self):
        self.env_info.PATH.append("myboostpath")
"""
        client.save({CONANFILE: boost})
        client.run("create . Boost/1.0@user/channel")
        other = """from conans import ConanFile
import os
class Other(ConanFile):
    requires = "Boost/1.0@user/channel"
    def build(self):
        self.output.info("OTHER PATH FOR BUILD %s" % os.getenv("PATH"))
    def package_info(self):
        self.env_info.PATH.append("myotherpath")
"""
        client.save({CONANFILE: other})
        client.run("create . Other/1.0@user/channel")
        lib = """from conans import ConanFile
import os
class Lib(ConanFile):
    build_requires = "Boost/1.0@user/channel", "Other/1.0@user/channel"
    def build(self):
        self.output.info("LIB PATH FOR BUILD %s" % os.getenv("PATH"))
"""
        client.save({CONANFILE: lib})
        client.run("create . Lib/1.0@user/channel")
        self.assertIn("LIB PATH FOR BUILD myotherpath%smyboostpath" % os.pathsep,
                      client.out)

    def test_transitive(self):
        client = TestClient()
        mingw = """from conans import ConanFile
class Tool(ConanFile):
    def package_info(self):
        self.env_info.PATH.append("mymingwpath")
"""
        myprofile = """
[build_requires]
mingw/0.1@lasote/stable
"""
        gtest = """from conans import ConanFile
import os
class Gtest(ConanFile):
    def build(self):
        self.output.info("GTEST PATH FOR BUILD %s" % os.getenv("PATH"))
"""
        app = """from conans import ConanFile
import os
class App(ConanFile):
    build_requires = "gtest/0.1@lasote/stable"
    def build(self):
        self.output.info("APP PATH FOR BUILD %s" % os.getenv("PATH"))
"""
        client.save({CONANFILE: mingw})
        client.run("create . mingw/0.1@lasote/stable")
        client.save({CONANFILE: gtest})
        client.run("export . gtest/0.1@lasote/stable")
        client.save({CONANFILE: app,
                     "myprofile": myprofile})
        client.run("create . app/0.1@lasote/stable --build=missing -pr=myprofile")
        self.assertIn("app/0.1@lasote/stable: APP PATH FOR BUILD mymingwpath",
                      client.out)
        self.assertIn("gtest/0.1@lasote/stable: GTEST PATH FOR BUILD mymingwpath",
                      client.out)

    def test_profile_order(self):
        client = TestClient()
        mingw = """from conans import ConanFile
class Tool(ConanFile):
    def package_info(self):
        self.env_info.PATH.append("mymingwpath")
"""
        msys = """from conans import ConanFile
class Tool(ConanFile):
    def package_info(self):
        self.env_info.PATH.append("mymsyspath")
"""
        myprofile1 = """
[build_requires]
mingw/0.1@lasote/stable
msys/0.1@lasote/stable
"""
        myprofile2 = """
[build_requires]
msys/0.1@lasote/stable
mingw/0.1@lasote/stable
"""

        app = """from conans import ConanFile
import os
class App(ConanFile):
    def build(self):
        self.output.info("APP PATH FOR BUILD %s" % os.getenv("PATH"))
"""
        client.save({CONANFILE: mingw})
        client.run("create . mingw/0.1@lasote/stable")
        client.save({CONANFILE: msys})
        client.run("create . msys/0.1@lasote/stable")
        client.save({CONANFILE: app,
                     "myprofile1": myprofile1,
                     "myprofile2": myprofile2})
        client.run("create . app/0.1@lasote/stable -pr=myprofile1")
        self.assertIn("app/0.1@lasote/stable: APP PATH FOR BUILD mymingwpath%smymsyspath"
                      % os.pathsep, client.out)
        client.run("create . app/0.1@lasote/stable -pr=myprofile2")
        self.assertIn("app/0.1@lasote/stable: APP PATH FOR BUILD mymsyspath%smymingwpath"
                      % os.pathsep, client.out)

    def test_require_itself(self):
        client = TestClient()
        mytool_conanfile = """from conans import ConanFile
class Tool(ConanFile):
    def build(self):
        self.output.info("BUILDING MYTOOL")
"""
        myprofile = """
[build_requires]
Tool/0.1@lasote/stable
"""
        client.save({CONANFILE: mytool_conanfile,
                     "profile.txt": myprofile})
        client.run("create . Tool/0.1@lasote/stable -pr=profile.txt")
        self.assertEqual(1, str(client.out).count("BUILDING MYTOOL"))

    @parameterized.expand([(requires, ), (requires_range, ), (requirements, ), (override, )])
    def test_build_requires(self, conanfile):
        client = TestClient()
        client.save({CONANFILE: tool_conanfile})
        client.run("export . lasote/stable")

        client.save({CONANFILE: conanfile}, clean_first=True)
        client.run("export . lasote/stable")

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
        client.run("export . lasote/stable")

        client.save({CONANFILE: conanfile,
                     "profile.txt": profile,
                     "profile2.txt": profile.replace("0.3", "[>0.2]")}, clean_first=True)
        client.run("export . lasote/stable")

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

    def options_test(self):
        conanfile = """from conans import ConanFile
class package(ConanFile):
    name            = "first"
    version         = "0.0.0"
    options         = {"coverage": [True, False]}
    default_options = "coverage=False"
    def build(self):
        self.output.info("Coverage: %s" % self.options.coverage)
    """
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("export . lasote/stable")

        consumer = """from conans import ConanFile

class package(ConanFile):
    name            = "second"
    version         = "0.0.0"
    default_options = "first:coverage=True"
    build_requires  = "first/0.0.0@lasote/stable"
"""
        client.save({"conanfile.py": consumer})
        client.run("install . --build=missing -o Pkg:someoption=3")
        self.assertIn("first/0.0.0@lasote/stable: Coverage: True", client.user_io.out)
