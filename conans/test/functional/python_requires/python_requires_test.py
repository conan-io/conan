import os
import textwrap
import time
import unittest

import pytest
from parameterized import parameterized

from conans.model.ref import ConanFileReference
from conans.paths import CONANFILE
from conans.test.utils.tools import TestClient, TestServer, \
    NO_SETTINGS_PACKAGE_ID, GenConanfile
from conans.test.utils.scm import create_local_git_repo


class PythonExtendTest(unittest.TestCase):
    def test_with_python_requires(self):
        # https://github.com/conan-io/conan/issues/5140
        client = TestClient()
        client.save({"conanfile.py": GenConanfile().with_name("dep").with_version("0.1")})
        client.run("export . user/testing")
        conanfile = textwrap.dedent("""
            from conans import ConanFile, python_requires
            p = python_requires("dep/0.1@user/testing")
            class APck(ConanFile):
                pass
            """)
        client.save({"conanfile.py": conanfile})
        client.run('editable add . pkg/0.1@user/testing')
        self.assertIn("Reference 'pkg/0.1@user/testing' in editable mode", client.out)
        client.run("editable remove pkg/0.1@user/testing")
        client.run("create . pkg/0.1@user/testing")
        client.run("copy pkg/0.1@user/testing company/stable")
        self.assertIn("Copied pkg/0.1@user/testing to pkg/0.1@company/stable", client.out)
        # imports should raise either
        client.run("install .")
        client.run("imports .")

    def _define_base(self, client):
        conanfile = """from conans import ConanFile
class MyConanfileBase(ConanFile):
    def source(self):
        self.output.info("My cool source!")
    def build(self):
        self.output.info("My cool build!")
    def package(self):
        self.output.info("My cool package!")
    def package_info(self):
        self.output.info("My cool package_info!")
"""
        client.save({"conanfile.py": conanfile})
        client.run("export . MyConanfileBase/1.1@lasote/testing")

    def test_with_alias(self):
        client = TestClient(servers={"default": TestServer()},
                            users={"default": [("lasote", "mypass")]})
        self._define_base(client)
        client.run("alias MyConanfileBase/LATEST@lasote/testing MyConanfileBase/1.1@lasote/testing")

        reuse = """from conans import python_requires
base = python_requires("MyConanfileBase/LATEST@lasote/testing")
class PkgTest(base.MyConanfileBase):
    pass
"""
        client.save({"conanfile.py": reuse}, clean_first=True)
        client.run("create . Pkg/0.1@lasote/testing")

    def test_reuse(self):
        client = TestClient(servers={"default": TestServer()},
                            users={"default": [("lasote", "mypass")]})
        self._define_base(client)
        reuse = """from conans import python_requires
base = python_requires("MyConanfileBase/1.1@lasote/testing")
class PkgTest(base.MyConanfileBase):
    pass
"""

        client.save({"conanfile.py": reuse}, clean_first=True)
        client.run("create . Pkg/0.1@lasote/testing")
        self.assertIn("Pkg/0.1@lasote/testing: My cool source!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: My cool build!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: My cool package!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: My cool package_info!", client.out)

        client.run("upload * --all --confirm")
        client.run("remove * -f")
        client.run("install Pkg/0.1@lasote/testing")
        self.assertIn("Pkg/0.1@lasote/testing: My cool package_info!", client.out)
        client.run("remove * -f")
        client.run("download Pkg/0.1@lasote/testing")
        self.assertIn("Pkg/0.1@lasote/testing: Package installed %s" % NO_SETTINGS_PACKAGE_ID,
                      client.out)

    def test_reuse_version_ranges(self):
        client = TestClient()
        self._define_base(client)
        reuse = """from conans import python_requires
base = python_requires("MyConanfileBase/[>1.0,<1.2]@lasote/testing")
class PkgTest(base.MyConanfileBase):
    pass
"""

        client.save({"conanfile.py": reuse}, clean_first=True)
        client.run("create . Pkg/0.1@lasote/testing")
        self.assertIn("Python requires", str(client.out).splitlines())
        self.assertIn("    MyConanfileBase/1.1@lasote/testing", str(client.out).splitlines())
        self.assertIn("Pkg/0.1@lasote/testing: My cool source!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: My cool build!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: My cool package!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: My cool package_info!", client.out)

    def test_invalid(self):
        client = TestClient()
        reuse = """from conans import ConanFile, python_requires
class PkgTest(ConanFile):
    def source(self):
        base = python_requires("MyConanfileBase/1.0@lasote/testing")
"""

        client.save({"conanfile.py": reuse})
        client.run("create . Pkg/0.1@lasote/testing", assert_error=True)
        self.assertIn("ERROR: Pkg/0.1@lasote/testing: Error in source() method, line 4", client.out)
        self.assertIn('base = python_requires("MyConanfileBase/1.0@lasote/testing', client.out)
        self.assertIn("ConanException: Invalid use of python_requires"
                      "(MyConanfileBase/1.0@lasote/testing)", client.out)

    def test_invalid2(self):
        client = TestClient()
        reuse = """import conans
class PkgTest(conans.ConanFile):
    def source(self):
        base = conans.python_requires("MyConanfileBase/1.0@lasote/testing")
"""

        client.save({"conanfile.py": reuse})
        client.run("create . Pkg/0.1@lasote/testing", assert_error=True)
        self.assertIn("ERROR: Pkg/0.1@lasote/testing: Error in source() method, line 4",
                      client.out)
        self.assertIn('base = conans.python_requires("MyConanfileBase/1.0@lasote/testing',
                      client.out)
        self.assertIn("ConanException: Invalid use of python_requires"
                      "(MyConanfileBase/1.0@lasote/testing)", client.out)

    def test_invalid3(self):
        client = TestClient()
        reuse = """from conans import ConanFile
from helpers import my_print

class PkgTest(ConanFile):
    exports = "helpers.py"
    def source(self):
        my_print()
"""
        base = """from conans import python_requires

def my_print():
    base = python_requires("MyConanfileBase/1.0@lasote/testing")
        """

        client.save({"conanfile.py": reuse, "helpers.py": base})
        client.run("create . Pkg/0.1@lasote/testing", assert_error=True)
        self.assertIn("ERROR: Pkg/0.1@lasote/testing: Error in source() method, line 7",
                      client.out)
        self.assertIn('my_print()', client.out)
        self.assertIn("ConanException: Invalid use of python_requires"
                      "(MyConanfileBase/1.0@lasote/testing)", client.out)

    def test_invalid4(self):
        client = TestClient()
        reuse = """from conans import ConanFile
from helpers import my_print

class PkgTest(ConanFile):
    exports = "helpers.py"
    def source(self):
        my_print()
    """
        base = """import conans
def my_print():
    base = conans.python_requires("MyConanfileBase/1.0@lasote/testing")
            """

        client.save({"conanfile.py": reuse, "helpers.py": base})
        client.run("create . Pkg/0.1@lasote/testing", assert_error=True)
        self.assertIn("ERROR: Pkg/0.1@lasote/testing: Error in source() method, line 7",
                      client.out)
        self.assertIn('my_print()', client.out)
        self.assertIn("ConanException: Invalid use of python_requires"
                      "(MyConanfileBase/1.0@lasote/testing)", client.out)

    def test_multiple_reuse(self):
        client = TestClient()
        conanfile = """from conans import ConanFile
class SourceBuild(ConanFile):
    def source(self):
        self.output.info("My cool source!")
    def build(self):
        self.output.info("My cool build!")
"""
        client.save({"conanfile.py": conanfile})
        client.run("export . SourceBuild/1.0@user/channel")

        conanfile = """from conans import ConanFile
class PackageInfo(ConanFile):
    def package(self):
        self.output.info("My cool package!")
    def package_info(self):
        self.output.info("My cool package_info!")
"""
        client.save({"conanfile.py": conanfile})
        client.run("export . PackageInfo/1.0@user/channel")

        conanfile = """from conans import ConanFile, python_requires
source = python_requires("SourceBuild/1.0@user/channel")
package = python_requires("PackageInfo/1.0@user/channel")
class MyConanfileBase(source.SourceBuild, package.PackageInfo):
    pass
"""
        client.save({"conanfile.py": conanfile})
        client.run("create . Pkg/0.1@lasote/testing")
        self.assertIn("Pkg/0.1@lasote/testing: My cool source!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: My cool build!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: My cool package!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: My cool package_info!", client.out)

    def test_transitive_py_requires(self):
        # https://github.com/conan-io/conan/issues/5529
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Base(ConanFile):
                pass
            """)
        client.save({"conanfile.py": conanfile})
        client.run("export . base/1.0@user/channel")

        conanfile = textwrap.dedent("""
            from conans import ConanFile, python_requires
            py_req = python_requires("base/1.0@user/channel")
            class PackageInfo(ConanFile):
                pass
            """)
        client.save({"conanfile.py": conanfile})
        client.run("export . helper/1.0@user/channel")

        conanfile = textwrap.dedent("""
            from conans import ConanFile, python_requires
            source = python_requires("helper/1.0@user/channel")
            class MyConanfileBase(ConanFile):
                pass
            """)
        client.save({"conanfile.py": conanfile})
        client.run("install . pkg/0.1@user/channel")
        lockfile = client.load("conan.lock")
        if client.cache.config.revisions_enabled:
            self.assertIn("base/1.0@user/channel#e41727b922c6ae54b216a58442893f3a", lockfile)
            self.assertIn("helper/1.0@user/channel#98457e1f8d9174ed053747634ce0ea1a", lockfile)
        else:
            self.assertIn("base/1.0@user/channel", lockfile)
            self.assertIn("helper/1.0@user/channel", lockfile)
        client.run("source .")
        self.assertIn("conanfile.py (pkg/0.1@user/channel): Configuring sources in", client.out)

    def test_multiple_requires_error(self):
        client = TestClient()
        conanfile = """from conans import ConanFile
myvar = 123
def myfunct():
    return 123
class Pkg(ConanFile):
    pass
"""
        client.save({"conanfile.py": conanfile})
        client.run("export . Pkg1/1.0@user/channel")

        conanfile = """from conans import ConanFile
myvar = 234
def myfunct():
    return 234
class Pkg(ConanFile):
    pass
"""
        client.save({"conanfile.py": conanfile})
        client.run("export . Pkg2/1.0@user/channel")

        conanfile = """from conans import ConanFile, python_requires
pkg1 = python_requires("Pkg1/1.0@user/channel")
pkg2 = python_requires("Pkg2/1.0@user/channel")
class MyConanfileBase(ConanFile):
    def build(self):
        self.output.info("PKG1 : %s" % pkg1.myvar)
        self.output.info("PKG2 : %s" % pkg2.myvar)
        self.output.info("PKG1F : %s" % pkg1.myfunct())
        self.output.info("PKG2F : %s" % pkg2.myfunct())
"""
        client.save({"conanfile.py": conanfile})
        client.run("create . Consumer/0.1@lasote/testing")
        self.assertIn("Consumer/0.1@lasote/testing: PKG1 : 123", client.out)
        self.assertIn("Consumer/0.1@lasote/testing: PKG2 : 234", client.out)
        self.assertIn("Consumer/0.1@lasote/testing: PKG1F : 123", client.out)
        self.assertIn("Consumer/0.1@lasote/testing: PKG2F : 234", client.out)

    def test_local_import(self):
        client = TestClient(servers={"default": TestServer()},
                            users={"default": [("lasote", "mypass")]})
        conanfile = """from conans import ConanFile
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
"""
        mydata = """src = "My cool source!"
build = "My cool build!"
pkg = "My cool package!"
info = "My cool package_info!"
"""
        client.save({"conanfile.py": conanfile,
                     "mydata.py": mydata})
        client.run("export . MyConanfileBase/1.1@lasote/testing")
        reuse = """from conans import ConanFile, python_requires
base = python_requires("MyConanfileBase/1.1@lasote/testing")
class PkgTest(base.MyConanfileBase):
    pass
"""

        client.save({"conanfile.py": reuse}, clean_first=True)
        client.run("create . Pkg/0.1@lasote/testing")
        self.assertIn("Pkg/0.1@lasote/testing: My cool source!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: My cool build!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: My cool package!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: My cool package_info!", client.out)

        client.run("upload * --all --confirm")
        client.run("remove * -f")
        client.run("install Pkg/0.1@lasote/testing")
        self.assertIn("Pkg/0.1@lasote/testing: My cool package_info!", client.out)
        client.run("remove * -f")
        client.run("download Pkg/0.1@lasote/testing")
        self.assertIn("Pkg/0.1@lasote/testing: Package installed %s" % NO_SETTINGS_PACKAGE_ID,
                      client.out)

    @pytest.mark.tool_git
    def test_reuse_scm(self):
        client = TestClient()

        conanfile = """from conans import ConanFile
scm = {"type" : "git",
       "url" : "somerepo",
       "revision" : "auto"}

class MyConanfileBase(ConanFile):
    scm = scm
"""
        create_local_git_repo({"conanfile.py": conanfile}, branch="my_release",
                              folder=client.current_folder)
        client.run("export . MyConanfileBase/1.1@lasote/testing")
        client.run("get MyConanfileBase/1.1@lasote/testing")
        # The global scm is left as-is
        self.assertIn("""scm = {"type" : "git",
       "url" : "somerepo",
       "revision" : "auto"}""", client.out)
        # but the class one is replaced
        self.assertNotIn("scm = scm", client.out)
        self.assertIn('    scm = {"revision":', client.out)
        self.assertIn('"type": "git",', client.out)
        self.assertIn('"url": "somerepo"', client.out)

        reuse = """from conans import python_requires
base = python_requires("MyConanfileBase/1.1@lasote/testing")
class PkgTest(base.MyConanfileBase):
    scm = base.scm
    other = 123
    def _my_method(self):
        pass
"""
        client.save({"conanfile.py": reuse})
        # Commit changes so it replaces and exports the scm data
        client.run_command('git add .')
        client.run_command('git commit -m "Modified conanfile"')

        client.run("export . Pkg/0.1@lasote/testing")
        client.run("get Pkg/0.1@lasote/testing")
        self.assertNotIn("scm = base.scm", client.out)
        self.assertIn('scm = {"revision":', client.out)
        self.assertIn('"type": "git",', client.out)
        self.assertIn('"url": "somerepo"', client.out)

    def test_reuse_class_members(self):
        client = TestClient()
        conanfile = """from conans import ConanFile
class MyConanfileBase(ConanFile):
    license = "MyLicense"
    author = "author@company.com"
    exports = "*.txt"
    exports_sources = "*.h"
    short_paths = True
    generators = "cmake"
"""
        client.save({"conanfile.py": conanfile})
        client.run("export . Base/1.1@lasote/testing")

        reuse = """from conans import python_requires
import os
base = python_requires("Base/1.1@lasote/testing")
class PkgTest(base.MyConanfileBase):
    def build(self):
        self.output.info("Exports sources! %s" % self.exports_sources)
        self.output.info("Short paths! %s" % self.short_paths)
        self.output.info("License! %s" % self.license)
        self.output.info("Author! %s" % self.author)
        assert os.path.exists("conanbuildinfo.cmake")
"""
        client.save({"conanfile.py": reuse,
                     "file.h": "header",
                     "other.txt": "text"})
        client.run("create . Pkg/0.1@lasote/testing")
        self.assertIn("Pkg/0.1@lasote/testing: Exports sources! *.h", client.out)
        self.assertIn("Pkg/0.1@lasote/testing exports: Copied 1 '.txt' file: other.txt",
                      client.out)
        self.assertIn("Pkg/0.1@lasote/testing exports_sources: Copied 1 '.h' file: file.h",
                      client.out)
        self.assertIn("Pkg/0.1@lasote/testing: Short paths! True", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: License! MyLicense", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: Author! author@company.com", client.out)
        ref = ConanFileReference.loads("Pkg/0.1@lasote/testing")
        self.assertTrue(os.path.exists(os.path.join(client.cache.package_layout(ref).export(),
                                                    "other.txt")))

    def test_reuse_name_version(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class BasePkg(ConanFile):
                name = "Base"
                version = "1.1"
            """)
        client.save({"conanfile.py": conanfile})
        client.run("export . lasote/testing")

        reuse = textwrap.dedent("""
            from conans import python_requires
            base = python_requires("Base/1.1@lasote/testing")
            class PkgTest(base.BasePkg):
                pass
            """)
        client.save({"conanfile.py": reuse})
        client.run("create . Pkg/0.1@lasote/testing", assert_error=True)
        self.assertIn("ERROR: Package recipe with name Pkg!=Base", client.out)

        reuse = textwrap.dedent("""
            from conans import python_requires
            base = python_requires("Base/1.1@lasote/testing")
            class PkgTest(base.BasePkg):
                name = "Pkg"
                version = "0.1"
            """)
        client.save({"conanfile.py": reuse})
        client.run("create . Pkg/0.1@lasote/testing")
        self.assertIn("Pkg/0.1@lasote/testing: Created package ", client.out)
        client.run("create . lasote/testing")
        self.assertIn("Pkg/0.1@lasote/testing: Created package ", client.out)

    def test_reuse_set_name_set_version(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile, load
            class BasePkg(ConanFile):
                def set_name(self):
                    self.name = load("name.txt")
                def set_version(self):
                    self.version = load("version.txt")
            """)
        client.save({"conanfile.py": conanfile,
                     "name.txt": "Base",
                     "version.txt": "1.1"})
        client.run("export . user/testing")

        reuse = textwrap.dedent("""
            from conans import python_requires
            base = python_requires("Base/1.1@user/testing")
            class PkgTest(base.BasePkg):
                pass
            """)
        client.save({"conanfile.py": reuse,
                     "name.txt": "Pkg",
                     "version.txt": "2.3"})
        client.run("create . user/testing")
        self.assertIn("Pkg/2.3@user/testing: Created package", client.out)

    def test_reuse_exports_conflict(self):
        conanfile = """from conans import ConanFile
class Base(ConanFile):
    exports_sources = "*.h"
"""
        client = TestClient()
        client.save({"conanfile.py": conanfile,
                     "header.h": "my header Base!!"})
        client.run("export . Base/0.1@user/testing")
        conanfile = """from conans import python_requires, load
base = python_requires("Base/0.1@user/testing")
class Pkg2(base.Base):
    def build(self):
        self.output.info("Exports sources: %s" % self.exports_sources)
        self.output.info("HEADER CONTENT!: %s" % load("header.h"))
"""
        client.save({"conanfile.py": conanfile,
                     "header.h": "my header Pkg!!"}, clean_first=True)
        client.run("create . Pkg/0.1@user/testing")
        self.assertIn("Pkg/0.1@user/testing: HEADER CONTENT!: my header Pkg!!", client.out)

    def test_transitive_imports_conflicts(self):
        # https://github.com/conan-io/conan/issues/3874
        client = TestClient()
        conanfile = """from conans import ConanFile
import myhelper
class SourceBuild(ConanFile):
    exports = "*.py"
"""
        helper = """def myhelp(output):
    output.info("MyHelperOutput!")
"""
        client.save({"conanfile.py": conanfile,
                     "myhelper.py": helper})
        client.run("export . base1/1.0@user/channel")
        client.save({"myhelper.py": helper.replace("MyHelperOutput!", "MyOtherHelperOutput!")})
        client.run("export . base2/1.0@user/channel")

        conanfile = """from conans import ConanFile, python_requires
base2 = python_requires("base2/1.0@user/channel")
base1 = python_requires("base1/1.0@user/channel")

class MyConanfileBase(ConanFile):
    def build(self):
        base1.myhelper.myhelp(self.output)
        base2.myhelper.myhelp(self.output)
"""
        # This should work, even if there is a local "myhelper.py" file, which could be
        # accidentaly imported (and it was, it was a bug)
        client.save({"conanfile.py": conanfile})
        client.run("create . Pkg/0.1@lasote/testing")
        self.assertIn("Pkg/0.1@lasote/testing: MyHelperOutput!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: MyOtherHelperOutput!", client.out)

        # Now, the same, but with "clean_first=True", should keep working
        client.save({"conanfile.py": conanfile}, clean_first=True)
        client.run("create . Pkg/0.1@lasote/testing")
        self.assertIn("Pkg/0.1@lasote/testing: MyHelperOutput!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: MyOtherHelperOutput!", client.out)

    def test_update(self):
        client = TestClient(servers={"default": TestServer()},
                            users={"default": [("lasote", "mypass")]})
        conanfile = """from conans import ConanFile
somevar = 42
class MyConanfileBase(ConanFile):
    pass
"""
        client.save({"conanfile.py": conanfile})
        client.run("export . MyConanfileBase/1.1@lasote/testing")
        client.run("upload * --confirm")

        client2 = TestClient(servers=client.servers, users={"default": [("lasote", "mypass")]})

        reuse = """from conans import python_requires
base = python_requires("MyConanfileBase/1.1@lasote/testing")
class PkgTest(base.MyConanfileBase):
    def configure(self):
        self.output.info("PYTHON REQUIRE VAR %s" % base.somevar)
"""

        client2.save({"conanfile.py": reuse})
        client2.run("install .")
        self.assertIn("conanfile.py: PYTHON REQUIRE VAR 42", client2.out)

        client.save({"conanfile.py": conanfile.replace("42", "143")})
        time.sleep(1)  # guarantee time offset
        client.run("export . MyConanfileBase/1.1@lasote/testing")
        client.run("upload * --confirm")

        client2.run("install . --update")
        self.assertIn("conanfile.py: PYTHON REQUIRE VAR 143", client2.out)

    def test_update_ranges(self):
        # https://github.com/conan-io/conan/issues/4650#issuecomment-497464305
        client = TestClient(servers={"default": TestServer()},
                            users={"default": [("lasote", "mypass")]})
        conanfile = """from conans import ConanFile
somevar = 42
class MyConanfileBase(ConanFile):
    pass
"""
        client.save({"conanfile.py": conanfile})
        client.run("export . MyConanfileBase/1.1@lasote/testing")
        client.run("upload * --confirm")

        client2 = TestClient(servers=client.servers, users={"default": [("lasote", "mypass")]})

        reuse = """from conans import python_requires
base = python_requires("MyConanfileBase/[>1.0]@lasote/testing")
class PkgTest(base.MyConanfileBase):
    def configure(self):
        self.output.info("PYTHON REQUIRE VAR %s" % base.somevar)
"""

        client2.save({"conanfile.py": reuse})
        client2.run("install .")
        self.assertIn("conanfile.py: PYTHON REQUIRE VAR 42", client2.out)

        client.save({"conanfile.py": conanfile.replace("42", "143")})
        # Make sure to bump the version!
        client.run("export . MyConanfileBase/1.2@lasote/testing")
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
            from conans import ConanFile, python_requires

            pyreq1 = python_requires("pyreq/1.0@user/channel")
            pyreq2 = python_requires("pyreq/2.0@user/channel")

            class Lib(ConanFile):
                pass
        """)
        t.save({"conanfile.py": conanfile})
        t.run("create . name/version@user/channel", assert_error=True)
        self.assertIn("ERROR: Error loading conanfile", t.out)
        self.assertIn("Same python_requires with different versions not allowed for a conanfile",
                      t.out)

    def test_short_paths(self):
        # https://github.com/conan-io/conan/issues/5814
        client = TestClient(default_server_user=True)
        conanfile = textwrap.dedent("""
        from conans import ConanFile
        class MyConanfileBase(ConanFile):
            exports = "*.txt"
            exports_sources = "*.h"
        """)
        client.save({"conanfile.py": conanfile,
                     "file.h": "header",
                     "other.txt": "text"})
        client.run("create . Base/1.2@lasote/testing")

        reuse = textwrap.dedent("""
        from conans import python_requires
        base = python_requires("Base/1.2@lasote/testing")
        class PkgTest(base.MyConanfileBase):
            short_paths = True
            name = "consumer"
            version = "1.0.0"
        """)
        client.save({"conanfile.py": reuse}, clean_first=True)
        client.run("create . lasote/testing")
        self.assertIn("consumer/1.0.0@lasote/testing: Created package revision", client.out)


class PythonRequiresNestedTest(unittest.TestCase):

    @parameterized.expand([(False, False), (True, False), (True, True), ])
    def test_python_requires_with_alias(self, use_alias, use_alias_of_alias):
        assert use_alias if use_alias_of_alias else True
        version_str = "latest2" if use_alias_of_alias else "latest" if use_alias else "1.0"
        client = TestClient()

        # Create python_requires
        client.save({CONANFILE: """
from conans import ConanFile

class PythonRequires0(ConanFile):

    def build(self):
        super(PythonRequires0, self).build()
        self.output.info(">>> PythonRequires0::build (v={{}})".format(self.version))
        """.format(v=version_str)})
        client.run("export . python_requires0/1.0@jgsogo/test")
        client.run("alias python_requires0/latest@jgsogo/test "
                   "python_requires0/1.0@jgsogo/test")
        client.run("alias python_requires0/latest2@jgsogo/test "
                   "python_requires0/latest@jgsogo/test")

        # Create python requires, that require the previous one
        client.save({CONANFILE: """
from conans import ConanFile, python_requires

base = python_requires("python_requires0/{v}@jgsogo/test")

class PythonRequires1(base.PythonRequires0):
    def build(self):
        super(PythonRequires1, self).build()
        self.output.info(">>> PythonRequires1::build (v={{}})".format(self.version))
        """.format(v=version_str)})
        client.run("export . python_requires1/1.0@jgsogo/test")
        client.run("alias python_requires1/latest@jgsogo/test python_requires1/1.0@jgsogo/test")
        client.run("alias python_requires1/latest2@jgsogo/test python_requires1/latest@jgsogo/test")

        # Create python requires
        client.save({CONANFILE: """
from conans import ConanFile, python_requires

class PythonRequires11(ConanFile):
    def build(self):
        super(PythonRequires11, self).build()
        self.output.info(">>> PythonRequires11::build (v={{}})".format(self.version))
        """.format(v=version_str)})
        client.run("export . python_requires11/1.0@jgsogo/test")
        client.run("alias python_requires11/latest@jgsogo/test python_requires11/1.0@jgsogo/test")
        client.run("alias python_requires11/latest2@jgsogo/test "
                   "python_requires11/latest@jgsogo/test")

        # Create python requires, that require the previous one
        client.save({CONANFILE: """
from conans import ConanFile, python_requires

base = python_requires("python_requires0/{v}@jgsogo/test")

class PythonRequires22(base.PythonRequires0):
    def build(self):
        super(PythonRequires22, self).build()
        self.output.info(">>> PythonRequires22::build (v={{}})".format(self.version))
        """.format(v=version_str)})
        client.run("export . python_requires22/1.0@jgsogo/test")
        client.run("alias python_requires22/latest@jgsogo/test python_requires22/1.0@jgsogo/test")
        client.run(
            "alias python_requires22/latest2@jgsogo/test python_requires22/latest@jgsogo/test")

        # Another python_requires, that requires the previous python requires
        client.save({CONANFILE: """
from conans import ConanFile, python_requires

base_class = python_requires("python_requires1/{v}@jgsogo/test")
base_class2 = python_requires("python_requires11/{v}@jgsogo/test")

class PythonRequires2(base_class.PythonRequires1, base_class2.PythonRequires11):

    def build(self):
        super(PythonRequires2, self).build()
        self.output.info(">>> PythonRequires2::build (v={{}})".format(self.version))
        """.format(v=version_str)})
        client.run("export . python_requires2/1.0@jgsogo/test")
        client.run("alias python_requires2/latest@jgsogo/test python_requires2/1.0@jgsogo/test")
        client.run("alias python_requires2/latest2@jgsogo/test python_requires2/latest@jgsogo/test")

        # My project, will consume the latest python requires
        client.save({CONANFILE: """
from conans import ConanFile, python_requires

base_class = python_requires("python_requires2/{v}@jgsogo/test")
base_class2 = python_requires("python_requires22/{v}@jgsogo/test")

class Project(base_class.PythonRequires2, base_class2.PythonRequires22):

    def build(self):
        super(Project, self).build()
        self.output.info(">>> Project::build (v={{}})".format(self.version))
        """.format(v=version_str)})

        client.run("create . project/1.0@jgsogo/test --build=missing")

        # Check that everything is being built
        self.assertIn("project/1.0@jgsogo/test: >>> PythonRequires11::build (v=1.0)", client.out)
        self.assertIn("project/1.0@jgsogo/test: >>> PythonRequires0::build (v=1.0)", client.out)
        self.assertIn("project/1.0@jgsogo/test: >>> PythonRequires22::build (v=1.0)", client.out)
        self.assertIn("project/1.0@jgsogo/test: >>> PythonRequires1::build (v=1.0)", client.out)
        self.assertIn("project/1.0@jgsogo/test: >>> PythonRequires2::build (v=1.0)", client.out)
        self.assertIn("project/1.0@jgsogo/test: >>> Project::build (v=1.0)", client.out)

        # Check that all the graph is printed properly
        #   - requirements
        self.assertIn("    project/1.0@jgsogo/test from local cache - Cache", client.out)
        #   - python requires
        self.assertIn("    python_requires11/1.0@jgsogo/test", client.out)
        self.assertIn("    python_requires0/1.0@jgsogo/test", client.out)
        self.assertIn("    python_requires22/1.0@jgsogo/test", client.out)
        self.assertIn("    python_requires1/1.0@jgsogo/test", client.out)
        self.assertIn("    python_requires2/1.0@jgsogo/test", client.out)
        #   - packages
        self.assertIn("    project/1.0@jgsogo/test:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Build",
                      client.out)

        #   - no mention to alias
        self.assertNotIn("alias", client.out)
        self.assertNotIn("alias2", client.out)

    def test_local_build(self):
        client = TestClient()
        client.save({"conanfile.py": "var=42\n"+
                                     str(GenConanfile().with_name("Tool").with_version("0.1"))})
        client.run("export . Tool/0.1@user/channel")

        conanfile = """from conans import ConanFile, python_requires
pkg1 = python_requires("Tool/0.1@user/channel")
class MyConanfileBase(ConanFile):
    def source(self):
        self.output.info("Pkg1 source: %s" % pkg1.var)
    def build(self):
        self.output.info("Pkg1 build: %s" % pkg1.var)
    def package(self):
        self.output.info("Pkg1 package: %s" % pkg1.var)
"""
        client.save({"conanfile.py": conanfile})
        client.run("source .")
        self.assertIn("conanfile.py: Pkg1 source: 42", client.out)
        client.run("install .")
        client.run("build .")
        self.assertIn("conanfile.py: Pkg1 build: 42", client.out)
        client.run("package .")
        self.assertIn("conanfile.py: Pkg1 package: 42", client.out)
        client.run("export-pkg . pkg1/0.1@user/testing")
