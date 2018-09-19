import unittest
from conans.test.utils.tools import TestClient
from conans.paths import CONANINFO
from conans.util.files import load
import os


class OptionsTest(unittest.TestCase):

    def general_scope_options_test_package_test(self):
        client = TestClient()
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    options = {"shared": ["1", "2"]}
    def configure(self):
        self.output.info("BUILD SHARED: %s" % self.options.shared)
"""
        test = """from conans import ConanFile
class Pkg(ConanFile):
    def test(self):
        pass
"""
        client.save({"conanfile.py": conanfile})
        client.run("create . Pkg/0.1@user/testing -o *:shared=1")
        self.assertIn("Pkg/0.1@user/testing: BUILD SHARED: 1", client.out)
        client.run("create . Pkg/0.1@user/testing -o shared=2")
        self.assertIn("Pkg/0.1@user/testing: BUILD SHARED: 2", client.out)
        # With test_package
        client.save({"conanfile.py": conanfile,
                     "test_package/conanfile.py": test})
        client.run("create . Pkg/0.1@user/testing -o *:shared=1")
        self.assertIn("Pkg/0.1@user/testing: BUILD SHARED: 1", client.out)
        client.run("create . Pkg/0.1@user/testing -o Pkg:shared=2")
        self.assertIn("Pkg/0.1@user/testing: BUILD SHARED: 2", client.out)
        error = client.run("create . Pkg/0.1@user/testing -o shared=1", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("'options.shared' doesn't exist", client.out)

        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    pass
"""
        client.save({"conanfile.py": conanfile}, clean_first=True)
        client.run("create . Pkg/0.1@user/testing -o *:shared=True")
        self.assertIn("Pkg/0.1@user/testing: Calling build()", client.out)
        error = client.run("create . Pkg/0.1@user/testing -o shared=False", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("'options.shared' doesn't exist", client.out)
        # With test_package
        client.save({"conanfile.py": conanfile,
                     "test_package/conanfile.py": test})
        client.run("create . Pkg/0.1@user/testing -o *:shared=True")
        self.assertIn("Pkg/0.1@user/testing: Calling build()", client.out)
        self.assertIn("Pkg/0.1@user/testing (test package): Running build()", client.out)

    def general_scope_priorities_test(self):
        client = TestClient()
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    options = {"shared": ["1", "2", "3"]}
    def configure(self):
        self.output.info("BUILD SHARED: %s" % self.options.shared)
"""
        test = """from conans import ConanFile
class Pkg(ConanFile):
    def test(self):
        pass
"""
        client.save({"conanfile.py": conanfile})
        # Consumer has priority
        client.run("create . Pkg/0.1@user/testing -o *:shared=1 -o shared=2")
        self.assertIn("Pkg/0.1@user/testing: BUILD SHARED: 2", client.out)
        # Consumer has priority over pattern, even if the pattern specifies the package name
        client.run("create . Pkg/0.1@user/testing -o *:shared=1 -o Pkg:shared=2 -o shared=3")
        self.assertIn("Pkg/0.1@user/testing: BUILD SHARED: 3", client.out)
        # With test_package
        client.save({"conanfile.py": conanfile,
                     "test_package/conanfile.py": test})
        # Sorted (longest, alphabetical) patterns, have priority
        client.run("create . Pkg/0.1@user/testing -o *:shared=1 -o Pkg:shared=2")
        self.assertIn("Pkg/0.1@user/testing: BUILD SHARED: 2", client.out)
        client.run("create . Pkg/0.1@user/testing  -o Pk*:shared=2 -o P*:shared=1")
        self.assertIn("Pkg/0.1@user/testing: BUILD SHARED: 2", client.out)
        client.run("create . Pkg/0.1@user/testing  -o Pk*:shared=2 -o P*:shared=1")
        self.assertIn("Pkg/0.1@user/testing: BUILD SHARED: 2", client.out)

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

    def general_scope_options_test(self):
        # https://github.com/conan-io/conan/issues/2538
        client = TestClient()
        conanfile_libA = """from conans import ConanFile
class LibA(ConanFile):
    options = {"shared": [True, False]}

    def configure(self):
        self.output.info("shared=%s" % self.options.shared)
    """
        client.save({"conanfile.py": conanfile_libA})
        client.run("create . libA/0.1@danimtb/testing -o *:shared=True")
        self.assertIn("libA/0.1@danimtb/testing: shared=True", client.out)

        conanfile_libB = """from conans import ConanFile
class LibB(ConanFile):
    options = {"shared": [True, False]}
    requires = "libA/0.1@danimtb/testing"

    def configure(self):
        self.options["*"].shared = self.options.shared
        self.output.info("shared=%s" % self.options.shared)
    """

        for without_configure_line in [True, False]:
            if without_configure_line:
                conanfile = conanfile_libB.replace(
                    "        self.options[\"*\"].shared = self.options.shared", "")

            client.save({"conanfile.py": conanfile})

            # Test info
            client.run("info . -o *:shared=True", ignore_error=True)
            self.assertIn("PROJECT: shared=True", client.out)
            self.assertIn("libA/0.1@danimtb/testing: shared=True", client.out)
            # Test create
            client.run("create . libB/0.1@danimtb/testing -o *:shared=True")
            self.assertIn("libB/0.1@danimtb/testing: shared=True", client.out)
            self.assertIn("libA/0.1@danimtb/testing: shared=True", client.out)
            # Test install
            client.run("install . -o *:shared=True")
            self.assertIn("PROJECT: shared=True", client.out)
            self.assertIn("libA/0.1@danimtb/testing: shared=True", client.out)
