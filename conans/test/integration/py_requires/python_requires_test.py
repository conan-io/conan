import os
import textwrap
import time
import unittest

from parameterized import parameterized

from conans.model.ref import ConanFileReference
from conans.paths import CONANFILE
from conans.test.utils.tools import TestClient, GenConanfile


class PyRequiresExtendTest(unittest.TestCase):

    @staticmethod
    def _define_base(client):
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class MyConanfileBase(ConanFile):
                def source(self):
                    self.output.info("My cool source!")
                def build(self):
                    self.output.info("My cool build!")
                def package(self):
                    self.output.info("My cool package!")
                def package_info(self):
                    self.output.info("My cool package_info!")
            """)
        client.save({"conanfile.py": conanfile})
        client.run("export . base/1.1@user/testing")

    def test_reuse(self):
        client = TestClient(default_server_user=True)
        self._define_base(client)
        reuse = textwrap.dedent("""
            from conans import ConanFile
            class PkgTest(ConanFile):
                python_requires = "base/1.1@user/testing"
                python_requires_extend = "base.MyConanfileBase"
            """)
        client.save({"conanfile.py": reuse}, clean_first=True)
        client.run("create . Pkg/0.1@user/testing")
        self.assertIn("Pkg/0.1@user/testing: My cool source!", client.out)
        self.assertIn("Pkg/0.1@user/testing: My cool build!", client.out)
        self.assertIn("Pkg/0.1@user/testing: My cool package!", client.out)
        self.assertIn("Pkg/0.1@user/testing: My cool package_info!", client.out)

        client.run("upload * --all --confirm")
        client.run("remove * -f")
        client.run("install Pkg/0.1@user/testing")
        self.assertIn("Pkg/0.1@user/testing: My cool package_info!", client.out)
        client.run("remove * -f")
        client.run("download Pkg/0.1@user/testing")
        self.assertIn("Pkg/0.1@user/testing: Package installed "
                      "69265e58ddc68274e0c5510905003ff78c9db5de", client.out)

    def test_reuse_dot(self):
        client = TestClient(default_server_user=True)
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class MyConanfileBase(ConanFile):
                def build(self):
                    self.output.info("My cool build!")
            """)
        client.save({"conanfile.py": conanfile})
        client.run("export . my.base/1.1@user/testing")
        reuse = textwrap.dedent("""
            from conans import ConanFile
            class PkgTest(ConanFile):
                python_requires = "my.base/1.1@user/testing"
                python_requires_extend = "my.base.MyConanfileBase"
            """)
        client.save({"conanfile.py": reuse}, clean_first=True)
        client.run("create . Pkg/0.1@user/testing")
        self.assertIn("Pkg/0.1@user/testing: My cool build!", client.out)

    def test_with_alias(self):
        client = TestClient()
        self._define_base(client)
        client.run("alias base/LATEST@user/testing base/1.1@user/testing")

        reuse = textwrap.dedent("""
            from conans import ConanFile
            class PkgTest(ConanFile):
                python_requires = "base/LATEST@user/testing"
                python_requires_extend = "base.MyConanfileBase"
            """)
        client.save({"conanfile.py": reuse}, clean_first=True)
        client.run("create . Pkg/0.1@user/testing")
        self.assertIn("Pkg/0.1@user/testing: My cool source!", client.out)
        self.assertIn("Pkg/0.1@user/testing: My cool build!", client.out)
        self.assertIn("Pkg/0.1@user/testing: My cool package!", client.out)
        self.assertIn("Pkg/0.1@user/testing: My cool package_info!", client.out)

    def test_reuse_version_ranges(self):
        client = TestClient()
        self._define_base(client)

        reuse = textwrap.dedent("""
            from conans import ConanFile
            class PkgTest(ConanFile):
                python_requires = "base/[>1.0,<1.2]@user/testing"
                python_requires_extend = "base.MyConanfileBase"
            """)

        client.save({"conanfile.py": reuse}, clean_first=True)
        client.run("create . Pkg/0.1@user/testing")
        self.assertIn("Python requires", str(client.out).splitlines())
        self.assertIn("    base/1.1@user/testing", str(client.out).splitlines())
        self.assertIn("Pkg/0.1@user/testing: My cool source!", client.out)
        self.assertIn("Pkg/0.1@user/testing: My cool build!", client.out)
        self.assertIn("Pkg/0.1@user/testing: My cool package!", client.out)
        self.assertIn("Pkg/0.1@user/testing: My cool package_info!", client.out)

    def test_multiple_reuse(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class SourceBuild(ConanFile):
                def source(self):
                    self.output.info("My cool source!")
                def build(self):
                    self.output.info("My cool build!")
            """)
        client.save({"conanfile.py": conanfile})
        client.run("export . SourceBuild/1.0@user/channel")

        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class PackageInfo(ConanFile):
                def package(self):
                    self.output.info("My cool package!")
                def package_info(self):
                    self.output.info("My cool package_info!")
            """)
        client.save({"conanfile.py": conanfile})
        client.run("export . PackageInfo/1.0@user/channel")

        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class MyConanfileBase(ConanFile):
                python_requires = "SourceBuild/1.0@user/channel", "PackageInfo/1.0@user/channel"
                python_requires_extend = "SourceBuild.SourceBuild", "PackageInfo.PackageInfo"
            """)
        client.save({"conanfile.py": conanfile})
        client.run("create . Pkg/0.1@user/testing")
        self.assertIn("Pkg/0.1@user/testing: My cool source!", client.out)
        self.assertIn("Pkg/0.1@user/testing: My cool build!", client.out)
        self.assertIn("Pkg/0.1@user/testing: My cool package!", client.out)
        self.assertIn("Pkg/0.1@user/testing: My cool package_info!", client.out)

    @staticmethod
    def test_transitive_access():
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("export . base/1.0@user/channel")

        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Helper(ConanFile):
                python_requires = "base/1.0@user/channel"
            """)
        client.save({"conanfile.py": conanfile})
        client.run("export . helper/1.0@user/channel")

        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                python_requires = "helper/1.0@user/channel"
                def build(self):
                    self.python_requires["base"]
            """)
        client.save({"conanfile.py": conanfile})
        client.run("create . pkg/0.1@user/channel")
        assert "pkg/0.1@user/channel: Created package" in client.out

        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                python_requires = "helper/1.0@user/channel"
                python_requires_extend = "base.HelloConan"
            """)
        client.save({"conanfile.py": conanfile})
        client.run("create . pkg/0.1@user/channel")
        assert "pkg/0.1@user/channel: Created package" in client.out

    def test_multiple_requires_error(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            myvar = 123
            def myfunct():
                return 123
            class Pkg(ConanFile):
                pass
            """)
        client.save({"conanfile.py": conanfile})
        client.run("export . pkg1/1.0@user/channel")

        conanfile = textwrap.dedent("""
            from conans import ConanFile
            myvar = 234
            def myfunct():
                return 234
            class Pkg(ConanFile):
                pass
            """)
        client.save({"conanfile.py": conanfile})
        client.run("export . pkg2/1.0@user/channel")

        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class MyConanfileBase(ConanFile):
                python_requires = "pkg1/1.0@user/channel", "pkg2/1.0@user/channel"
                def build(self):
                    self.output.info("PKG1 N: %s" % self.python_requires["pkg1"].conanfile.name)
                    self.output.info("PKG1 V: %s" % self.python_requires["pkg1"].conanfile.version)
                    self.output.info("PKG1 U: %s" % self.python_requires["pkg1"].conanfile.user)
                    self.output.info("PKG1 C: %s" % self.python_requires["pkg1"].conanfile.channel)
                    self.output.info("PKG1 : %s" % self.python_requires["pkg1"].module.myvar)
                    self.output.info("PKG2 : %s" % self.python_requires["pkg2"].module.myvar)
                    self.output.info("PKG1F : %s" % self.python_requires["pkg1"].module.myfunct())
                    self.output.info("PKG2F : %s" % self.python_requires["pkg2"].module.myfunct())
            """)
        client.save({"conanfile.py": conanfile})
        client.run("create . Consumer/0.1@user/testing")
        self.assertIn("Consumer/0.1@user/testing: PKG1 N: pkg1", client.out)
        self.assertIn("Consumer/0.1@user/testing: PKG1 V: 1.0", client.out)
        self.assertIn("Consumer/0.1@user/testing: PKG1 U: user", client.out)
        self.assertIn("Consumer/0.1@user/testing: PKG1 C: channel", client.out)
        self.assertIn("Consumer/0.1@user/testing: PKG1 : 123", client.out)
        self.assertIn("Consumer/0.1@user/testing: PKG2 : 234", client.out)
        self.assertIn("Consumer/0.1@user/testing: PKG1F : 123", client.out)
        self.assertIn("Consumer/0.1@user/testing: PKG2F : 234", client.out)

    def test_local_import(self):
        client = TestClient(default_server_user=True)
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            import mydata
            class MyConanfileBase(ConanFile):
                exports = "*.py"
                def source(self):
                    self.output.info(mydata.src)
                def build(self):
                    self.output.info(mydata.build)
                def package(self):
                    self.output.info(mydata.pkg)
                def package_info(self):
                    self.output.info(mydata.info)
            """)
        mydata = textwrap.dedent("""
            src = "My cool source!"
            build = "My cool build!"
            pkg = "My cool package!"
            info = "My cool package_info!"
            """)
        client.save({"conanfile.py": conanfile,
                     "mydata.py": mydata})
        client.run("export . base/1.1@user/testing")
        reuse = textwrap.dedent("""
            from conans import ConanFile
            class PkgTest(ConanFile):
                python_requires = "base/1.1@user/testing"
                python_requires_extend = "base.MyConanfileBase"
            """)

        client.save({"conanfile.py": reuse}, clean_first=True)
        client.run("create . Pkg/0.1@user/testing")
        self.assertIn("Pkg/0.1@user/testing: My cool source!", client.out)
        self.assertIn("Pkg/0.1@user/testing: My cool build!", client.out)
        self.assertIn("Pkg/0.1@user/testing: My cool package!", client.out)
        self.assertIn("Pkg/0.1@user/testing: My cool package_info!", client.out)

        client.run("upload * --all --confirm")
        client.run("remove * -f")
        client.run("install Pkg/0.1@user/testing")
        self.assertIn("Pkg/0.1@user/testing: My cool package_info!", client.out)
        client.run("remove * -f")
        client.run("download Pkg/0.1@user/testing")
        self.assertIn("Pkg/0.1@user/testing: Package installed "
                      "69265e58ddc68274e0c5510905003ff78c9db5de", client.out)

    def test_reuse_class_members(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class MyConanfileBase(ConanFile):
                license = "MyLicense"
                author = "author@company.com"
                exports = "*.txt"
                exports_sources = "*.h"
                short_paths = True
                generators = "cmake"
            """)
        client.save({"conanfile.py": conanfile,
                     "header.h": "some content"})
        client.run("export . base/1.1@user/testing")

        reuse = textwrap.dedent("""
            from conans import ConanFile
            from conans.tools import load
            import os
            class PkgTest(ConanFile):
                python_requires = "base/1.1@user/testing"
                python_requires_extend = "base.MyConanfileBase"
                def build(self):
                    self.output.info("Exports sources! %s" % self.exports_sources)
                    self.output.info("HEADER CONTENT!: %s" % load("header.h"))
                    self.output.info("Short paths! %s" % self.short_paths)
                    self.output.info("License! %s" % self.license)
                    self.output.info("Author! %s" % self.author)
                    assert os.path.exists("conanbuildinfo.cmake")
            """)
        client.save({"conanfile.py": reuse,
                     "header.h": "pkg new header contents",
                     "other.txt": "text"})
        client.run("create . Pkg/0.1@user/testing")
        self.assertIn("Pkg/0.1@user/testing: Exports sources! *.h", client.out)
        self.assertIn("Pkg/0.1@user/testing exports: Copied 1 '.txt' file: other.txt",
                      client.out)
        self.assertIn("Pkg/0.1@user/testing exports_sources: Copied 1 '.h' file: header.h",
                      client.out)
        self.assertIn("Pkg/0.1@user/testing: Short paths! True", client.out)
        self.assertIn("Pkg/0.1@user/testing: License! MyLicense", client.out)
        self.assertIn("Pkg/0.1@user/testing: Author! author@company.com", client.out)
        self.assertIn("Pkg/0.1@user/testing: HEADER CONTENT!: pkg new header contents", client.out)
        ref = ConanFileReference.loads("Pkg/0.1@user/testing")
        self.assertTrue(os.path.exists(os.path.join(client.cache.package_layout(ref).export(),
                                                    "other.txt")))

    def test_reuse_system_requirements(self):
        # https://github.com/conan-io/conan/issues/7718
        client = TestClient()
        conanfile = textwrap.dedent("""
           from conans import ConanFile
           class MyConanfileBase(ConanFile):
               def system_requirements(self):
                   self.output.info("My system_requirements %s being called!" % self.name)
           """)
        client.save({"conanfile.py": conanfile})
        client.run("export . base/1.1@user/testing")
        reuse = textwrap.dedent("""
            from conans import ConanFile
            class PkgTest(ConanFile):
                python_requires = "base/1.1@user/testing"
                python_requires_extend = "base.MyConanfileBase"
            """)
        client.save({"conanfile.py": reuse}, clean_first=True)
        client.run("create . Pkg/0.1@user/testing")
        self.assertIn("Pkg/0.1@user/testing: My system_requirements Pkg being called!", client.out)

    def test_overwrite_class_members(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class MyConanfileBase(ConanFile):
                license = "MyLicense"
                author = "author@company.com"
                settings = "os", # tuple!
            """)
        client.save({"conanfile.py": conanfile})
        client.run("export . base/1.1@user/testing")

        reuse = textwrap.dedent("""
            from conans import ConanFile
            class PkgTest(ConanFile):
                license = "MIT"
                author = "frodo"
                settings = "arch", # tuple!
                python_requires = "base/1.1@user/testing"
                python_requires_extend = "base.MyConanfileBase"

                def init(self):
                    base = self.python_requires["base"].module.MyConanfileBase
                    self.settings = base.settings + self.settings
                    self.license = base.license

                def build(self):
                    self.output.info("License! %s" % self.license)
                    self.output.info("Author! %s" % self.author)
                    self.output.info("os: %s arch: %s" % (self.settings.get_safe("os"),
                                                          self.settings.arch))
            """)
        client.save({"conanfile.py": reuse})
        client.run("create . Pkg/0.1@user/testing -s os=Windows -s arch=armv7")
        self.assertIn("Pkg/0.1@user/testing: License! MyLicense", client.out)
        self.assertIn("Pkg/0.1@user/testing: Author! frodo", client.out)
        self.assertIn("Pkg/0.1@user/testing: os: Windows arch: armv7", client.out)

    def test_failure_init_method(self):
        client = TestClient()
        base = textwrap.dedent("""
            from conans import ConanFile
            class MyBase(object):
                settings = "os", "build_type", "arch"
                options = {"base_option": [True, False]}
                default_options = {"base_option": False}

            class BaseConanFile(ConanFile):
                pass
            """)
        client.save({"conanfile.py": base})
        client.run("export . base/1.0@")
        derived = textwrap.dedent("""
            from conans import ConanFile
            class DerivedConan(ConanFile):
                settings = "os", "build_type", "arch"

                python_requires = "base/1.0"
                python_requires_extend = 'base.MyBase'

                options = {"derived_option": [True, False]}
                default_options = {"derived_option": False}

                def init(self):
                    base = self.python_requires['base'].module.MyBase
                    self.options.update(base.options)
                    self.default_options.update(base.default_options)
                """)
        client.save({"conanfile.py": derived})
        client.run("create . pkg/0.1@ -o base_option=True")
        self.assertIn("pkg/0.1: Created package", client.out)

    def test_transitive_imports_conflicts(self):
        # https://github.com/conan-io/conan/issues/3874
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            import myhelper
            class SourceBuild(ConanFile):
                exports = "*.py"
            """)
        helper = textwrap.dedent("""
            def myhelp(output):
                output.info("MyHelperOutput!")
            """)
        client.save({"conanfile.py": conanfile,
                     "myhelper.py": helper})
        client.run("export . base1/1.0@user/channel")
        client.save({"myhelper.py": helper.replace("MyHelperOutput!", "MyOtherHelperOutput!")})
        client.run("export . base2/1.0@user/channel")

        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class MyConanfileBase(ConanFile):
                python_requires = "base2/1.0@user/channel", "base1/1.0@user/channel"
                def build(self):
                    self.python_requires["base1"].module.myhelper.myhelp(self.output)
                    self.python_requires["base2"].module.myhelper.myhelp(self.output)
            """)
        # This should work, even if there is a local "myhelper.py" file, which could be
        # accidentaly imported (and it was, it was a bug)
        client.save({"conanfile.py": conanfile})
        client.run("create . Pkg/0.1@user/testing")
        self.assertIn("Pkg/0.1@user/testing: MyHelperOutput!", client.out)
        self.assertIn("Pkg/0.1@user/testing: MyOtherHelperOutput!", client.out)

        # Now, the same, but with "clean_first=True", should keep working
        client.save({"conanfile.py": conanfile}, clean_first=True)
        client.run("create . Pkg/0.1@user/testing")
        self.assertIn("Pkg/0.1@user/testing: MyHelperOutput!", client.out)
        self.assertIn("Pkg/0.1@user/testing: MyOtherHelperOutput!", client.out)

    def test_update(self):
        client = TestClient(default_server_user=True)
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            somevar = 42
            class MyConanfileBase(ConanFile):
                pass
            """)
        client.save({"conanfile.py": conanfile})
        client.run("export . base/1.1@user/testing")
        client.run("upload * --confirm")

        client2 = TestClient(servers=client.servers, users={"default": [("user", "mypass")]})
        reuse = textwrap.dedent("""
            from conans import ConanFile
            class PkgTest(ConanFile):
                python_requires = "base/1.1@user/testing"
                python_requires_extend = "base.MyConanfileBase"
                def configure(self):
                    self.output.info("PYTHON REQUIRE VAR %s"
                                     % self.python_requires["base"].module.somevar)
        """)

        client2.save({"conanfile.py": reuse})
        client2.run("install .")
        self.assertIn("conanfile.py: PYTHON REQUIRE VAR 42", client2.out)

        client.save({"conanfile.py": conanfile.replace("42", "143")})
        time.sleep(1)  # guarantee time offset
        client.run("export . base/1.1@user/testing")
        client.run("upload * --confirm")

        client2.run("install . --update")
        self.assertIn("conanfile.py: PYTHON REQUIRE VAR 143", client2.out)

    def test_update_ranges(self):
        # Same as the above, but using a version range, and no --update
        # https://github.com/conan-io/conan/issues/4650#issuecomment-497464305
        client = TestClient(default_server_user=True)
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            somevar = 42
            class MyConanfileBase(ConanFile):
                pass
            """)
        client.save({"conanfile.py": conanfile})
        client.run("export . base/1.1@user/testing")
        client.run("upload * --confirm")

        client2 = TestClient(servers=client.servers, users={"default": [("user", "password")]})
        reuse = textwrap.dedent("""
            from conans import ConanFile
            class PkgTest(ConanFile):
                python_requires = "base/[>1.0]@user/testing"
                python_requires_extend = "base.MyConanfileBase"
                def configure(self):
                    self.output.info("PYTHON REQUIRE VAR %s"
                                     % self.python_requires["base"].module.somevar)
        """)

        client2.save({"conanfile.py": reuse})
        client2.run("install .")
        self.assertIn("conanfile.py: PYTHON REQUIRE VAR 42", client2.out)

        client.save({"conanfile.py": conanfile.replace("42", "143")})
        # Make sure to bump the version!
        client.run("export . base/1.2@user/testing")
        client.run("upload * --confirm")

        client2.run("install . --update")
        self.assertIn("conanfile.py: PYTHON REQUIRE VAR 143", client2.out)

    def test_duplicate_pyreq(self):
        t = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class PyReq(ConanFile):
                pass
        """)
        t.save({"conanfile.py": conanfile})
        t.run("export . pyreq/1.0@user/channel")
        t.run("export . pyreq/2.0@user/channel")

        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Lib(ConanFile):
                python_requires = "pyreq/1.0@user/channel", "pyreq/2.0@user/channel"
        """)
        t.save({"conanfile.py": conanfile})
        t.run("create . name/version@user/channel", assert_error=True)
        self.assertIn("ERROR: Error loading conanfile", t.out)
        self.assertIn("The python_require 'pyreq' already exists", t.out)

    def test_local_build(self):
        client = TestClient()
        client.save({"conanfile.py": "var=42\n"+str(GenConanfile())})
        client.run("export . tool/0.1@user/channel")
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class MyConanfileBase(ConanFile):
                python_requires = "tool/0.1@user/channel"
                def source(self):
                    self.output.info("Pkg1 source: %s" % self.python_requires["tool"].module.var)
                def build(self):
                    self.output.info("Pkg1 build: %s" % self.python_requires["tool"].module.var)
                def package(self):
                    self.output.info("Pkg1 package: %s" % self.python_requires["tool"].module.var)
            """)
        client.save({"conanfile.py": conanfile})
        client.run("source .")
        self.assertIn("conanfile.py: Pkg1 source: 42", client.out)
        client.run("install .")
        client.run("build .")
        self.assertIn("conanfile.py: Pkg1 build: 42", client.out)
        client.run("package .")
        self.assertIn("conanfile.py: Pkg1 package: 42", client.out)
        client.run("export-pkg . pkg1/0.1@user/testing")

    def test_reuse_name_version(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            from conans.tools import load
            import os

            class Source(object):
                def set_name(self):
                    self.name = load("name.txt")

                def set_version(self):
                    self.version = load("version.txt")

            class MyConanfileBase(ConanFile):
                pass
            """)
        client.save({"conanfile.py": conanfile})
        client.run("export . tool/0.1@user/channel")
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class MyConanfileBase(ConanFile):
                python_requires = "tool/0.1@user/channel"
                python_requires_extend = "tool.Source"
                def source(self):
                    self.output.info("Pkg1 source: %s:%s" % (self.name, self.version))
                def build(self):
                    self.output.info("Pkg1 build: %s:%s" % (self.name, self.version))
                def package(self):
                    self.output.info("Pkg1 package: %s:%s" % (self.name, self.version))
            """)
        client.save({"conanfile.py": conanfile,
                     "name.txt": "MyPkg",
                     "version.txt": "MyVersion"})
        client.run("export .")
        self.assertIn("MyPkg/MyVersion: A new conanfile.py version was exported", client.out)
        client.run("create .")
        self.assertIn("MyPkg/MyVersion: Pkg1 source: MyPkg:MyVersion", client.out)
        self.assertIn("MyPkg/MyVersion: Pkg1 build: MyPkg:MyVersion", client.out)
        self.assertIn("MyPkg/MyVersion: Pkg1 package: MyPkg:MyVersion", client.out)

    @parameterized.expand([(False, False), (True, False), (True, True), ])
    def test_python_requires_with_alias(self, use_alias, use_alias_of_alias):
        assert use_alias if use_alias_of_alias else True
        version_str = "latest2" if use_alias_of_alias else "latest" if use_alias else "1.0"
        client = TestClient()

        # Create python_requires
        client.save({CONANFILE: textwrap.dedent("""
            from conans import ConanFile
            class PythonRequires0(ConanFile):
                def build(self):
                    super(PythonRequires0, self).build()
                    self.output.info("PythonRequires0::build")
                    """)})
        client.run("export . python_requires0/1.0@user/test")
        client.run("alias python_requires0/latest@user/test python_requires0/1.0@user/test")
        client.run("alias python_requires0/latest2@user/test python_requires0/latest@user/test")

        # Create python requires, that require the previous one
        client.save({CONANFILE: textwrap.dedent("""
            from conans import ConanFile
            class PythonRequires1(ConanFile):
                python_requires = "python_requires0/{v}@user/test"
                python_requires_extend = "python_requires0.PythonRequires0"
                def build(self):
                    super(PythonRequires1, self).build()
                    self.output.info("PythonRequires1::build")
            """).format(v=version_str)})
        client.run("export . python_requires1/1.0@user/test")
        client.run("alias python_requires1/latest@user/test python_requires1/1.0@user/test")
        client.run("alias python_requires1/latest2@user/test python_requires1/latest@user/test")

        # Create python requires
        client.save({CONANFILE: textwrap.dedent("""
            from conans import ConanFile
            class PythonRequires11(ConanFile):
                def build(self):
                    super(PythonRequires11, self).build()
                    self.output.info("PythonRequires11::build")
                    """)})
        client.run("export . python_requires11/1.0@user/test")
        client.run("alias python_requires11/latest@user/test python_requires11/1.0@user/test")
        client.run("alias python_requires11/latest2@user/test python_requires11/latest@user/test")

        # Create python requires, that require the previous one
        client.save({CONANFILE: textwrap.dedent("""
            from conans import ConanFile
            class PythonRequires22(ConanFile):
                python_requires = "python_requires0/{v}@user/test"
                python_requires_extend = "python_requires0.PythonRequires0"
                def build(self):
                    super(PythonRequires22, self).build()
                    self.output.info("PythonRequires22::build")
                    """).format(v=version_str)})
        client.run("export . python_requires22/1.0@user/test")
        client.run("alias python_requires22/latest@user/test python_requires22/1.0@user/test")
        client.run("alias python_requires22/latest2@user/test python_requires22/latest@user/test")

        # Another python_requires, that requires the previous python requires
        client.save({CONANFILE: textwrap.dedent("""
            from conans import ConanFile
            class PythonRequires2(ConanFile):
                python_requires = "python_requires1/{v}@user/test", "python_requires11/{v}@user/test"
                python_requires_extend = ("python_requires1.PythonRequires1",
                                      "python_requires11.PythonRequires11")
                def build(self):
                    super(PythonRequires2, self).build()
                    self.output.info("PythonRequires2::build")
                    """).format(v=version_str)})
        client.run("export . python_requires2/1.0@user/test")
        client.run("alias python_requires2/latest@user/test python_requires2/1.0@user/test")
        client.run("alias python_requires2/latest2@user/test python_requires2/latest@user/test")

        # My project, will consume the latest python requires
        client.save({CONANFILE: textwrap.dedent("""
            from conans import ConanFile
            class Project(ConanFile):
                python_requires = "python_requires2/{v}@user/test", "python_requires22/{v}@user/test"
                python_requires_extend = ("python_requires2.PythonRequires2",
                                          "python_requires22.PythonRequires22")
                def build(self):
                    super(Project, self).build()
                    self.output.info("Project::build")
                    """).format(v=version_str)})

        client.run("create . project/1.0@user/test --build=missing")

        # Check that everything is being built
        self.assertIn("project/1.0@user/test: PythonRequires11::build", client.out)
        self.assertIn("project/1.0@user/test: PythonRequires0::build", client.out)
        self.assertIn("project/1.0@user/test: PythonRequires22::build", client.out)
        self.assertIn("project/1.0@user/test: PythonRequires1::build", client.out)
        self.assertIn("project/1.0@user/test: PythonRequires2::build", client.out)
        self.assertIn("project/1.0@user/test: Project::build", client.out)

        # Check that all the graph is printed properly
        #   - requirements
        self.assertIn("    project/1.0@user/test from local cache - Cache", client.out)
        #   - python requires
        self.assertIn("    python_requires11/1.0@user/test", client.out)
        self.assertIn("    python_requires0/1.0@user/test", client.out)
        self.assertIn("    python_requires22/1.0@user/test", client.out)
        self.assertIn("    python_requires1/1.0@user/test", client.out)
        self.assertIn("    python_requires2/1.0@user/test", client.out)
        #   - packages
        self.assertIn("    project/1.0@user/test:88cd9e14eae0af6c823ed619608b6883037e5cbc - Build",
                      client.out)

        #   - no mention to alias
        self.assertNotIn("alias", client.out)
        self.assertNotIn("alias2", client.out)

    def test_reuse_export_sources(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class MyConanfileBase(ConanFile):
                exports = "*"
            """)
        client.save({"conanfile.py": conanfile,
                     "file.h": "myheader",
                     "folder/other.h": "otherheader"})
        client.run("export . tool/0.1@user/channel")
        conanfile = textwrap.dedent("""
            from conans import ConanFile, load
            import os
            class MyConanfileBase(ConanFile):
                python_requires = "tool/0.1@user/channel"
                def source(self):
                    sources = self.python_requires["tool"].path
                    file_h = os.path.join(sources, "file.h")
                    other_h = os.path.join(sources, "folder/other.h")
                    self.output.info("Source: tool header: %s" % load(file_h))
                    self.output.info("Source: tool other: %s" % load(other_h))
                def build(self):
                    sources = self.python_requires["tool"].path
                    file_h = os.path.join(sources, "file.h")
                    other_h = os.path.join(sources, "folder/other.h")
                    self.output.info("Build: tool header: %s" % load(file_h))
                    self.output.info("Build: tool other: %s" % load(other_h))
                def package(self):
                    sources = self.python_requires["tool"].path
                    file_h = os.path.join(sources, "file.h")
                    other_h = os.path.join(sources, "folder/other.h")
                    self.output.info("Package: tool header: %s" % load(file_h))
                    self.output.info("Package: tool other: %s" % load(other_h))
            """)
        client.save({"conanfile.py": conanfile,
                     "name.txt": "MyPkg",
                     "version.txt": "MyVersion"})
        client.run("export . pkg/1.0@user/channel")
        self.assertIn("pkg/1.0@user/channel: A new conanfile.py version was exported", client.out)
        client.run("create . pkg/1.0@user/channel")
        self.assertIn("pkg/1.0@user/channel: Source: tool header: myheader", client.out)
        self.assertIn("pkg/1.0@user/channel: Source: tool other: otherheader", client.out)
        self.assertIn("pkg/1.0@user/channel: Build: tool header: myheader", client.out)
        self.assertIn("pkg/1.0@user/channel: Build: tool other: otherheader", client.out)
        self.assertIn("pkg/1.0@user/channel: Package: tool header: myheader", client.out)
        self.assertIn("pkg/1.0@user/channel: Package: tool other: otherheader", client.out)

        # The local flow
        client.run("install .")
        client.run("source .")
        self.assertIn("conanfile.py: Source: tool header: myheader", client.out)
        self.assertIn("conanfile.py: Source: tool other: otherheader", client.out)
        client.run("build .")
        self.assertIn("conanfile.py: Build: tool header: myheader", client.out)
        self.assertIn("conanfile.py: Build: tool other: otherheader", client.out)

    def test_reuse_exports(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class MyConanfileBase(ConanFile):
                exports = "*"
            """)
        client.save({"conanfile.py": conanfile,
                     "file.h": "myheader",
                     "folder/other.h": "otherheader"})
        client.run("editable add . tool/0.1@user/channel")

        conanfile = textwrap.dedent("""
            from conans import ConanFile, load
            import os
            class MyConanfileBase(ConanFile):
                python_requires = "tool/0.1@user/channel"
                def source(self):
                    sources = self.python_requires["tool"].path
                    file_h = os.path.join(sources, "file.h")
                    other_h = os.path.join(sources, "folder/other.h")
                    self.output.info("Source: tool header: %s" % load(file_h))
                    self.output.info("Source: tool other: %s" % load(other_h))
                def build(self):
                    sources = self.python_requires["tool"].path
                    file_h = os.path.join(sources, "file.h")
                    other_h = os.path.join(sources, "folder/other.h")
                    self.output.info("Build: tool header: %s" % load(file_h))
                    self.output.info("Build: tool other: %s" % load(other_h))
            """)

        client2 = TestClient(cache_folder=client.cache_folder)
        client2.save({"conanfile.py": conanfile,
                      "name.txt": "MyPkg",
                      "version.txt": "MyVersion"})

        # The local flow
        client2.run("install .")
        client2.run("source .")
        self.assertIn("conanfile.py: Source: tool header: myheader", client2.out)
        self.assertIn("conanfile.py: Source: tool other: otherheader", client2.out)
        client2.run("build .")
        self.assertIn("conanfile.py: Build: tool header: myheader", client2.out)
        self.assertIn("conanfile.py: Build: tool other: otherheader", client2.out)

    def test_build_id(self):
        client = TestClient(default_server_user=True)
        self._define_base(client)
        reuse = textwrap.dedent("""
            from conans import ConanFile
            class PkgTest(ConanFile):
                python_requires = "base/1.1@user/testing"
                python_requires_extend = "base.MyConanfileBase"
                def build_id(self):
                    pass
            """)
        client.save({"conanfile.py": reuse}, clean_first=True)
        client.run("create . Pkg/0.1@user/testing")
        self.assertIn("Pkg/0.1@user/testing: My cool source!", client.out)
        self.assertIn("Pkg/0.1@user/testing: My cool build!", client.out)
        self.assertIn("Pkg/0.1@user/testing: My cool package!", client.out)
        self.assertIn("Pkg/0.1@user/testing: My cool package_info!", client.out)


def test_transitive_python_requires():
    # https://github.com/conan-io/conan/issues/8546
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        myvar = 123
        def myfunct():
            return 234
        class SharedFunction(ConanFile):
            name = "shared-function"
            version = "1.0"
        """)
    client.save({"conanfile.py": conanfile})
    client.run("export . @user/channel")

    conanfile = textwrap.dedent("""
        from conans import ConanFile
        class BaseClass(ConanFile):
            name = "base-class"
            version = "1.0"
            python_requires = "shared-function/1.0@user/channel"
            def build(self):
                pyreqs = self.python_requires
                v = pyreqs["shared-function"].module.myvar  # v will be 123
                f = pyreqs["shared-function"].module.myfunct()  # f will be 234
                self.output.info("%s, %s" % (v, f))
        """)
    client.save({"conanfile.py": conanfile})
    client.run("export . user/channel")

    conanfile = textwrap.dedent("""
        from conans import ConanFile
        class Consumer(ConanFile):
            name = "consumer"
            version = "1.0"
            python_requires = "base-class/1.0@user/channel"
            python_requires_extend = "base-class.BaseClass"
        """)
    client.save({"conanfile.py": conanfile})
    client.run("create . @user/channel")
    assert "consumer/1.0@user/channel: Calling build()\nconsumer/1.0@user/channel: 123, 234" in \
           client.out


def test_transitive_diamond_python_requires():
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        myvar = 123
        def myfunct():
            return 234
        class SharedFunction(ConanFile):
            name = "shared-function"
            version = "1.0"
        """)
    client.save({"conanfile.py": conanfile})
    client.run("export . @user/channel")

    conanfile = textwrap.dedent("""
        from conans import ConanFile
        myvar = 222
        def myfunct():
            return 2222
        class SharedFunction2(ConanFile):
            name = "shared-function2"
            version = "1.0"
        """)
    client.save({"conanfile.py": conanfile})
    client.run("export . @user/channel")

    conanfile = textwrap.dedent("""
        from conans import ConanFile
        class BaseClass(ConanFile):
            name = "base-class"
            version = "1.0"
            python_requires = "shared-function/1.0@user/channel", "shared-function2/1.0@user/channel"
            def build(self):
                pyreqs = self.python_requires
                v = pyreqs["shared-function"].module.myvar  # v will be 123
                f = pyreqs["shared-function2"].module.myfunct()  # f will be 2222
                self.output.info("%s, %s" % (v, f))
        """)
    client.save({"conanfile.py": conanfile})
    client.run("export . user/channel")

    conanfile = textwrap.dedent("""
        from conans import ConanFile
        class BaseClass2(ConanFile):
            name = "base-class2"
            version = "1.0"
            python_requires = "shared-function/1.0@user/channel", "shared-function2/1.0@user/channel"
            def package(self):
                pyreqs = self.python_requires
                v = pyreqs["shared-function2"].module.myvar  # v will be 222
                f = pyreqs["shared-function"].module.myfunct()  # f will be 234
                self.output.info("%s, %s" % (v, f))
        """)
    client.save({"conanfile.py": conanfile})
    client.run("export . user/channel")

    conanfile = textwrap.dedent("""
        from conans import ConanFile
        class Consumer(ConanFile):
            name = "consumer"
            version = "1.0"
            python_requires = "base-class/1.0@user/channel", "base-class2/1.0@user/channel"
            python_requires_extend = "base-class.BaseClass", "base-class2.BaseClass2"
        """)
    client.save({"conanfile.py": conanfile})
    client.run("create . @user/channel")
    assert "consumer/1.0@user/channel: Calling build()\nconsumer/1.0@user/channel: 123, 2222" in \
           client.out
    assert "consumer/1.0@user/channel: Calling package()\nconsumer/1.0@user/channel: 222, 234" in \
           client.out


def test_multiple_reuse():
    """ test how to enable the multiple code reuse for custom user generators
        # https://github.com/conan-io/conan/issues/11589
    """

    c = TestClient()
    common = textwrap.dedent("""
        from conan import ConanFile
        def mycommon():
            return 42
        class Common(ConanFile):
            name = "common"
            version = "0.1"
        """)
    tool = textwrap.dedent("""
        from conan import ConanFile

        class MyGenerator:
            common = None
            def __init__(self, conanfile):
                self.conanfile = conanfile
            def generate(self):
                self.conanfile.output.info("VALUE TOOL: {}!!!".format(MyGenerator.common.mycommon()))

        class Tool(ConanFile):
            name = "tool"
            version = "0.1"
            python_requires = "common/0.1"
            def init(self):
                MyGenerator.common = self.python_requires["common"].module
        """)
    consumer = textwrap.dedent("""
        from conan import ConanFile
        class Consumer(ConanFile):
            python_requires = "tool/0.1", "common/0.1"
            def generate(self):
                mycommon = self.python_requires["common"].module.mycommon
                self.output.info("VALUE COMMON: {}!!!".format(mycommon()))
                mygenerator = self.python_requires["tool"].module.MyGenerator(self)
                mygenerator.generate()
        """)
    c.save({"common/conanfile.py": common,
            "tool/conanfile.py": tool,
            "consumer/conanfile.py": consumer})
    c.run("export common")
    c.run("export tool")
    c.run("install consumer")
    assert "VALUE COMMON: 42!!!" in c.out
    assert "VALUE TOOL: 42!!!" in c.out
