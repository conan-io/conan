import textwrap
import unittest

from conans.paths import CONANINFO
from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestClient, GenConanfile


class OptionsTest(unittest.TestCase):

    def test_general_scope_options_test_package(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                options = {"shared": ["1", "2"]}
                def configure(self):
                    self.output.info("BUILD SHARED: %s" % self.options.shared)
            """)
        test = GenConanfile().with_test("pass")
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
        client.run("create . Pkg/0.1@user/testing -o shared=1", assert_error=True)
        self.assertIn("option 'shared' doesn't exist", client.out)

    def test_general_scope_options_test_package_notdefined(self):
        client = TestClient()
        conanfile = GenConanfile()
        client.save({"conanfile.py": conanfile})
        client.run("create . Pkg/0.1@user/testing -o *:shared=True")
        self.assertIn("Pkg/0.1@user/testing: Calling build()", client.out)
        client.run("create . Pkg/0.1@user/testing -o shared=False", assert_error=True)
        self.assertIn("option 'shared' doesn't exist", client.out)
        # With test_package
        client.save({"conanfile.py": conanfile,
                     "test_package/conanfile.py": GenConanfile().with_test("pass")})
        client.run("create . Pkg/0.1@user/testing -o *:shared=True")
        self.assertIn("Pkg/0.1@user/testing: Calling build()", client.out)
        self.assertIn("Pkg/0.1@user/testing (test package): Calling build()", client.out)

    def test_general_scope_priorities(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                options = {"shared": ["1", "2", "3"]}
                def configure(self):
                    self.output.info("BUILD SHARED: %s" % self.options.shared)
            """)
        client.save({"conanfile.py": conanfile})
        # Consumer has priority
        client.run("create . Pkg/0.1@user/testing -o *:shared=1 -o shared=2")
        self.assertIn("Pkg/0.1@user/testing: BUILD SHARED: 2", client.out)
        # Consumer has priority over pattern, even if the pattern specifies the package name
        client.run("create . Pkg/0.1@user/testing -o *:shared=1 -o Pkg:shared=2 -o shared=3")
        self.assertIn("Pkg/0.1@user/testing: BUILD SHARED: 3", client.out)
        # With test_package
        client.save({"conanfile.py": conanfile,
                     "test_package/conanfile.py": GenConanfile().with_test("pass")})
        # Sorted (longest, alphabetical) patterns, have priority
        client.run("create . Pkg/0.1@user/testing -o *:shared=1 -o Pkg:shared=2")
        self.assertIn("Pkg/0.1@user/testing: BUILD SHARED: 2", client.out)
        client.run("create . Pkg/0.1@user/testing  -o Pk*:shared=2 -o P*:shared=1")
        self.assertIn("Pkg/0.1@user/testing: BUILD SHARED: 2", client.out)
        client.run("create . Pkg/0.1@user/testing  -o Pk*:shared=2 -o P*:shared=1")
        self.assertIn("Pkg/0.1@user/testing: BUILD SHARED: 2", client.out)

    def test_parsing(self):
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
        self.assertIn("OPTION a=b", client.out)

    def test_basic_caching(self):
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
                      client.out)
        conaninfo = client.load(CONANINFO)
        self.assertIn("zlib:shared=True", conaninfo)

        # Options not cached anymore
        client.run("install . --build=missing")
        self.assertIn("zlib/0.1@lasote/testing:%s" % NO_SETTINGS_PACKAGE_ID,
                      client.out)
        conaninfo = client.load(CONANINFO)
        self.assertNotIn("zlib:shared=True", conaninfo)

    def test_default_options(self):
        client = TestClient()
        conanfile = """
from conans import ConanFile

class MyConanFile(ConanFile):
    name = "MyConanFile"
    version = "1.0"
    options = {"config": %s}
    default_options = "config%s"

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
        client.run("create . danimtb/testing", assert_error=True)
        self.assertIn("Error while initializing options.", client.out)
        client.save({"conanfile.py": conanfile % ("\"ANY\"", "=None")})
        client.run("create . danimtb/testing")
        self.assertNotIn("Boolean evaluation", client.out)
        self.assertNotIn("None evaluation", client.out)
        self.assertIn("String evaluation", client.out)

        # Using None as possible options
        client.save({"conanfile.py": conanfile % ("[None]", "")})
        client.run("create . danimtb/testing", assert_error=True)
        self.assertIn("Error while initializing options.", client.out)
        client.save({"conanfile.py": conanfile % ("[None]", "=None")})
        client.run("create . danimtb/testing")
        self.assertNotIn("Boolean evaluation", client.out)
        self.assertNotIn("None evaluation", client.out)
        self.assertIn("String evaluation", client.out)

        # Using "None" as possible options
        client.save({"conanfile.py": conanfile % ("[\"None\"]", "")})
        client.run("create . danimtb/testing", assert_error=True)
        self.assertIn("Error while initializing options.", client.out)
        client.save({"conanfile.py": conanfile % ("[\"None\"]", "=None")})
        client.run("create . danimtb/testing")
        self.assertNotIn("Boolean evaluation", client.out)
        self.assertNotIn("None evaluation", client.out)
        self.assertIn("String evaluation", client.out)
        client.save({"conanfile.py": conanfile % ("[\"None\"]", "=\\\"None\\\"")})
        client.run("create . danimtb/testing", assert_error=True)
        self.assertIn("'\"None\"' is not a valid 'options.config' value", client.out)

        # Using "ANY" as possible options and "otherstringvalue" as default
        client.save({"conanfile.py": conanfile % ("[\"otherstringvalue\"]", "")})
        client.run("create . danimtb/testing", assert_error=True)
        self.assertIn("Error while initializing options.", client.out)
        client.save({"conanfile.py": conanfile % ("\"ANY\"", "=otherstringvalue")})
        client.run("create . danimtb/testing")
        self.assertIn("Boolean evaluation", client.out)
        self.assertNotIn("None evaluation", client.out)
        self.assertNotIn("String evaluation", client.out)

    def test_general_scope_options(self):
        # https://github.com/conan-io/conan/issues/2538
        client = TestClient()
        conanfile_liba = textwrap.dedent("""
            from conans import ConanFile
            class LibA(ConanFile):
                options = {"shared": [True, False]}

                def configure(self):
                    self.output.info("shared=%s" % self.options.shared)
                """)
        client.save({"conanfile.py": conanfile_liba})
        client.run("create . libA/0.1@danimtb/testing -o *:shared=True")
        self.assertIn("libA/0.1@danimtb/testing: shared=True", client.out)

        conanfile_libb = textwrap.dedent("""
            from conans import ConanFile
            class LibB(ConanFile):
                options = {"shared": [True, False]}
                requires = "libA/0.1@danimtb/testing"

                def configure(self):
                    self.options["*"].shared = self.options.shared
                    self.output.info("shared=%s" % self.options.shared)
                """)

        for without_configure_line in [True, False]:
            if without_configure_line:
                conanfile = conanfile_libb.replace("self.options[", "#")
            else:
                conanfile = conanfile_libb
            client.save({"conanfile.py": conanfile})

            # Test info
            client.run("info . -o *:shared=True")
            self.assertIn("conanfile.py: shared=True", client.out)
            self.assertIn("libA/0.1@danimtb/testing: shared=True", client.out)
            # Test create
            client.run("create . libB/0.1@danimtb/testing -o *:shared=True")
            self.assertIn("libB/0.1@danimtb/testing: shared=True", client.out)
            self.assertIn("libA/0.1@danimtb/testing: shared=True", client.out)
            # Test install
            client.run("install . -o *:shared=True")
            self.assertIn("conanfile.py: shared=True", client.out)
            self.assertIn("libA/0.1@danimtb/testing: shared=True", client.out)

    def test_overridable_shared_option(self):
        client = TestClient()
        conanfile = GenConanfile().with_option("shared", [True, False])\
                                  .with_default_option("shared", "False")
        client.save({"conanfile.py": conanfile})
        client.run("create . liba/0.1@user/testing -o liba:shared=False")
        client.run("create . liba/0.1@user/testing -o liba:shared=True")
        consumer = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                requires = "liba/0.1@user/testing"
                options = {"shared": [True, False]}
                default_options = {"shared": False}
                def configure(self):
                    if self.options.shared:
                        self.options["*"].shared = True

                def package_id(self):
                    self.info.shared_library_package_id()
        """)
        client.save({"conanfile.py": consumer})

        # LibA STATIC
        for options in ("",
                        "-o pkg:shared=False",
                        "-o liba:shared=False",
                        "-o pkg:shared=True  -o liba:shared=False",
                        "-o pkg:shared=False -o liba:shared=False"):
            client.run("create . pkg/0.1@user/testing %s" % options)
            self.assertIn("liba/0.1@user/testing:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache",
                          client.out)

        # LibA SHARED
        for options in ("-o pkg:shared=True",
                        "-o pkg:shared=True -o liba:shared=True",
                        "-o pkg:shared=False -o liba:shared=True"):
            client.run("create . pkg/0.1@user/testing %s" % options)
            self.assertIn("liba/0.1@user/testing:2a623e3082a38f90cd2c3d12081161412de331b0 - Cache",
                          client.out)

        # Pkg STATIC
        for options in ("",
                        "-o pkg:shared=False",
                        "-o liba:shared=False",
                        "-o liba:shared=True",
                        "-o pkg:shared=False  -o liba:shared=False",
                        "-o pkg:shared=False -o liba:shared=False"):
            client.run("create . pkg/0.1@user/testing %s" % options)
            self.assertIn("pkg/0.1@user/testing:c74ab38053f265e63a1f3d819a41bc4b8332a6fc - Build",
                          client.out)

        # Pkg SHARED, libA SHARED
        for options in ("-o pkg:shared=True",
                        "-o pkg:shared=True  -o liba:shared=True"):
            client.run("create . pkg/0.1@user/testing %s" % options)
            self.assertIn("pkg/0.1@user/testing:fcaf52c0d66c3d68e6b6ae6330acafbcaae7dacf - Build",
                          client.out)

        # Pkg SHARED, libA STATIC
        options = "-o pkg:shared=True  -o liba:shared=False"
        client.run("create . pkg/0.1@user/testing %s" % options)
        self.assertIn("pkg/0.1@user/testing:5e7619965702ca25bdff1b2ce672a8236b8da689 - Build",
                      client.out)

    def test_overridable_no_shared_option(self):
        client = TestClient()
        conanfile = GenConanfile()
        client.save({"conanfile.py": conanfile})
        client.run("create . liba/0.1@user/testing")
        consumer = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                requires = "liba/0.1@user/testing"
                options = {"shared": [True, False]}
                default_options = {"shared": False}
                def configure(self):
                    if self.options.shared:
                        self.options["*"].shared = True

                def package_id(self):
                    self.info.shared_library_package_id()
        """)
        client.save({"conanfile.py": consumer})
        # LibA STATIC
        for options in ("",
                        "-o pkg:shared=False",
                        "-o pkg:shared=True"):
            client.run("create . pkg/0.1@user/testing %s" % options)
            self.assertIn("liba/0.1@user/testing:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache",
                          client.out)

    def test_missing_shared_option_package_id(self):
        client = TestClient()

        consumer = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                def package_id(self):
                    self.info.shared_library_package_id()
            """)
        client.save({"conanfile.py": consumer})
        client.run("create . pkg/0.1@user/testing")
        self.assertIn("pkg/0.1@user/testing: Created package ", client.out)
