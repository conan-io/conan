import unittest
from conans.test.utils.tools import TestClient
from conans.paths import CONANINFO
from conans.util.files import load
import os


class OptionsTest(unittest.TestCase):

    def parsing_test(self):
        client = TestClient()
        conanfile = '''
from conans import ConanFile
class EqualerrorConan(ConanFile):
    name = "equal"
    version = "1.0.0"
    options = {"opt": "ANY"}
    default_options = ("opt=b=c",)

    def build(self):
        self.output.warn("OPTION %s" % self.options.opt)
'''
        client.save({"conanfile.py": conanfile})
        client.run("export . user/testing")
        conanfile = '''
[requires]
equal/1.0.0@user/testing
[options]
equal:opt=a=b
'''
        client.save({"conanfile.txt": conanfile}, clean_first=True)
        client.run("install . --build=missing")
        self.assertIn("OPTION a=b", client.user_io.out)

    def basic_caching_test(self):
        client = TestClient()
        zlib = '''
from conans import ConanFile

class ConanLib(ConanFile):
    name = "zlib"
    version = "0.1"
    options = {"shared": [True, False]}
    default_options= "shared=False"
'''

        client.save({"conanfile.py": zlib})
        client.run("export . lasote/testing")

        project = """[requires]
zlib/0.1@lasote/testing
"""
        client.save({"conanfile.txt": project}, clean_first=True)

        client.run("install . -o zlib:shared=True --build=missing")
        self.assertIn("zlib/0.1@lasote/testing:2a623e3082a38f90cd2c3d12081161412de331b0",
                      client.user_io.out)
        conaninfo = load(os.path.join(client.current_folder, CONANINFO))
        self.assertIn("zlib:shared=True", conaninfo)

        # Options not cached anymore
        client.run("install . --build=missing")
        self.assertIn("zlib/0.1@lasote/testing:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9",
                      client.user_io.out)
        conaninfo = load(os.path.join(client.current_folder, CONANINFO))
        self.assertNotIn("zlib:shared=True", conaninfo)

    def default_options_test(self):
        client = TestClient()
        conanfile = """
from conans import ConanFile

class MyConanFile(ConanFile):
    name = "MyConanFile"
    version = "1.0"
    options = {"config": %s}
    default_options = "config=%s"

    def configure(self):
        if self.options.config:
            self.output.info("Boolean evaluation")
        if self.options.config is None:
            self.output.info("None evaluation")
        if self.options.config == "None":
            self.output.info("String evaluation")
"""
        # Using "ANY" as possible options
        client.save({"conanfile.py": conanfile % ("\"ANY\"", "")})
        error = client.run("create . danimtb/testing", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("Please define a default value for 'config' in'default_options'", client.out)
        client.save({"conanfile.py": conanfile % ("\"ANY\"", "None")})
        client.run("create . danimtb/testing")
        self.assertNotIn("Boolean evaluation", client.out)
        self.assertNotIn("None evaluation", client.out)
        self.assertIn("String evaluation", client.out)

        # Using None as possible options
        client.save({"conanfile.py": conanfile % ("[None]", "")})
        error = client.run("create . danimtb/testing", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("Please define a default value for 'config' in'default_options'", client.out)
        client.save({"conanfile.py": conanfile % ("[None]", "None")})
        client.run("create . danimtb/testing")
        self.assertNotIn("Boolean evaluation", client.out)
        self.assertNotIn("None evaluation", client.out)
        self.assertIn("String evaluation", client.out)

        # Using "None" as possible options
        client.save({"conanfile.py": conanfile % ("[\"None\"]", "")})
        error = client.run("create . danimtb/testing", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("Please define a default value for 'config' in'default_options'", client.out)
        client.save({"conanfile.py": conanfile % ("[\"None\"]", "None")})
        client.run("create . danimtb/testing")
        self.assertNotIn("Boolean evaluation", client.out)
        self.assertNotIn("None evaluation", client.out)
        self.assertIn("String evaluation", client.out)
        client.save({"conanfile.py": conanfile % ("[\"None\"]", "\\\"None\\\"")})
        error = client.run("create . danimtb/testing", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("'\"None\"' is not a valid 'options.config' value", client.out)

        # Using "ANY" as possible options and "otherstringvalue" as default
        client.save({"conanfile.py": conanfile % ("[\"otherstringvalue\"]", "")})
        error = client.run("create . danimtb/testing", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("Please define a default value for 'config' in'default_options'", client.out)
        client.save({"conanfile.py": conanfile % ("\"ANY\"", "otherstringvalue")})
        client.run("create . danimtb/testing")
        self.assertIn("Boolean evaluation", client.out)
        self.assertNotIn("None evaluation", client.out)
        self.assertNotIn("String evaluation", client.out)
    def general_scope_options_test(self):
        # https://github.com/conan-io/conan/issues/2538
        client = TestClient()
        conanfile_libA = """
from conans import ConanFile

class LibA(ConanFile):
    name = "libA"
    version = "0.1"
    options = {"shared": [True, False]}
    default_options= "shared=False"

    def configure(self):
        self.output.info("shared=%s" % self.options.shared)
    """
        conanfile_libB = """
from conans import ConanFile

class LibB(ConanFile):
    name = "libB"
    version = "0.1"
    options = {"shared": [True, False]}
    default_options= "shared=False"
    requires = "libA/0.1@danimtb/testing"

    def configure(self):
        self.options["*"].shared = self.options.shared
        self.output.info("shared=%s" % self.options.shared)
    """
        client.save({"conanfile_liba.py": conanfile_libA,
                     "conanfile_libb.py": conanfile_libB})

        for without_configure_line in [True, False]:
            client.save({"conanfile_liba.py": conanfile_libA})

            if without_configure_line:
                client.save({"conanfile_libb.py": conanfile_libB.replace(
                    "        self.options[\"*\"].shared = self.options.shared", "")})
            else:
                client.save({"conanfile_libb.py": conanfile_libB})

            # Test info
            client.run("export conanfile_liba.py danimtb/testing")
            client.run("info conanfile_libb.py -o *:shared=True")
            self.assertIn("PROJECT: shared=True", client.out)
            self.assertIn("libA/0.1@danimtb/testing: shared=True", client.out)
            # Test create
            client.run("create conanfile_liba.py danimtb/testing -o *:shared=True")
            client.run("create conanfile_libb.py danimtb/testing -o *:shared=True")
            self.assertIn("libB/0.1@danimtb/testing: shared=True", client.out)
            self.assertIn("libA/0.1@danimtb/testing: shared=True", client.out)
            # Test install
            client.run("install conanfile_libb.py -o *:shared=True")
            self.assertIn("PROJECT: shared=True", client.out)
            self.assertIn("libA/0.1@danimtb/testing: shared=True", client.out)
