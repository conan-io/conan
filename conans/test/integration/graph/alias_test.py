import os
import textwrap
import unittest

import pytest
from parameterized.parameterized import parameterized

from conans.model.recipe_ref import RecipeReference
from conans.test.utils.tools import TestClient, TestServer, GenConanfile


@pytest.mark.xfail(reason="To be moved to core graph tests")
class ConanAliasTest(unittest.TestCase):

    def test_complete_large(self):
        # https://github.com/conan-io/conan/issues/2583
        conanfile0 = """from conan import ConanFile
class Pkg(ConanFile):
    pass
"""
        conanfile = """from conan import ConanFile
class Pkg(ConanFile):
    def requirements(self):
        self.requires("%s")
"""
        conanfile2 = """from conan import ConanFile
class Pkg(ConanFile):
    def requirements(self):
        self.requires("%s")
        self.requires("%s")
"""
        conanfile3 = """from conan import ConanFile
class Pkg(ConanFile):
    def requirements(self):
        self.requires("%s")
        self.requires("%s")
        self.requires("%s")
"""
        client = TestClient()

        def export_alias(name, conanfile):
            client.save({"conanfile.py": conanfile})
            client.run("export . --name=%s --version=0.1 --user=user --channel=testing" % name)
            client.alias("%s/ALIAS@user/testing %s/0.1@user/testing" % (name, name))

        for name, conanfile in [
            ("CA", conanfile0),
            ("CB", conanfile % "CA/ALIAS@user/testing"),
            ("CC", conanfile % "CA/ALIAS@user/testing"),
            ("CD", conanfile2 % ("CA/ALIAS@user/testing", "CB/ALIAS@user/testing")),
            ("CE", conanfile2 % ("CA/ALIAS@user/testing", "CB/ALIAS@user/testing")),
            ("CF", conanfile2 % ("CA/ALIAS@user/testing", "CB/ALIAS@user/testing")),
            ("CG", conanfile3 %
                ("CA/ALIAS@user/testing", "CD/ALIAS@user/testing", "CB/ALIAS@user/testing")),
            ("CI", conanfile2 % ("CA/ALIAS@user/testing", "CB/ALIAS@user/testing")),
            ("CH", conanfile2 % ("CA/ALIAS@user/testing", "CB/ALIAS@user/testing")),
        ]:
            export_alias(name, conanfile)

        cj = """from conan import ConanFile
class Pkg(ConanFile):
    def build_requirements( self):
        self.requires( "CA/ALIAS@user/testing")
    def requirements( self):
        self.requires( "CB/ALIAS@user/testing")
"""
        export_alias("CJ", cj)

        ck = """from conan import ConanFile
class Pkg(ConanFile):
    def build_requirements( self):
        self.requires( "CA/ALIAS@user/testing")

    def requirements( self):
        self.requires( "CB/ALIAS@user/testing")
        self.requires( "CH/ALIAS@user/testing")
        self.requires( "CI/ALIAS@user/testing")
        self.requires( "CF/ALIAS@user/testing")
        self.requires( "CE/ALIAS@user/testing")
        self.requires( "CD/ALIAS@user/testing")
        self.requires( "CJ/ALIAS@user/testing")
        self.requires( "CG/ALIAS@user/testing")
"""
        export_alias("CK", ck)

        cl = """from conan import ConanFile
class Pkg(ConanFile):
    def build_requirements( self):
        self.requires( "CA/ALIAS@user/testing")

    def requirements( self):
        self.requires( "CI/ALIAS@user/testing")
        self.requires( "CF/ALIAS@user/testing")
        self.requires( "CC/ALIAS@user/testing")
        self.requires( "CJ/ALIAS@user/testing")
        self.requires( "CB/ALIAS@user/testing")
        self.requires( "CH/ALIAS@user/testing")
        self.requires( "CK/ALIAS@user/testing")
"""
        export_alias("CL", cl)

        cm = """from conan import ConanFile
class Pkg(ConanFile):
    def build_requirements( self):
        self.requires( "CA/ALIAS@user/testing")

    def requirements( self):
        self.requires( "CB/ALIAS@user/testing")
        self.requires( "CL/ALIAS@user/testing")
"""
        export_alias("CM", cm)

        consumer = """from conan import ConanFile
class Pkg(ConanFile):
    def build_requirements( self):
        self.requires( "CA/ALIAS@user/testing")

    def requirements( self):
        self.requires( "CD/ALIAS@user/testing")
        self.requires( "CI/ALIAS@user/testing")
        self.requires( "CG/ALIAS@user/testing")
        self.requires( "CM/ALIAS@user/testing")
        self.requires( "CJ/ALIAS@user/testing")
        self.requires( "CK/ALIAS@user/testing")
        self.requires( "CB/ALIAS@user/testing")
        self.requires( "CL/ALIAS@user/testing")
        self.requires( "CH/ALIAS@user/testing")
"""
        client.save({"conanfile.py": consumer})
        client.run("info . --graph=file.dot")
        graphfile = client.load("file.dot")
        self.assertIn('"conanfile.py" -> "CD/0.1@user/testing"', graphfile)
        self.assertIn('"CB/0.1@user/testing" -> "CA/0.1@user/testing"', graphfile)
        self.assertIn('"CD/0.1@user/testing" -> "CA/0.1@user/testing"', graphfile)
        self.assertIn('"CD/0.1@user/testing" -> "CB/0.1@user/testing"', graphfile)
        self.assertIn('"CJ/0.1@user/testing" -> "CB/0.1@user/testing"', graphfile)

    def test_striped_large(self):
        # https://github.com/conan-io/conan/issues/2583
        conanfile0 = """from conan import ConanFile
class Pkg(ConanFile):
    pass
"""
        client = TestClient()

        def export_alias(name, conanfile):
            client.save({"conanfile.py": conanfile})
            client.run("export . --name=%s --version=0.1 --user=user --channel=testing" % name)
            client.alias("%s/ALIAS@user/testing %s/0.1@user/testing" % (name, name))

        export_alias("CH", conanfile0)

        ck = """from conan import ConanFile
class Pkg(ConanFile):
    def requirements( self):
        self.requires( "CH/ALIAS@user/testing")
"""
        export_alias("CK", ck)

        cl = """from conan import ConanFile
class Pkg(ConanFile):
    def requirements( self):
        self.requires( "CK/ALIAS@user/testing")
        self.requires( "CH/ALIAS@user/testing")
"""
        export_alias("CL", cl)

        cm = """from conan import ConanFile
class Pkg(ConanFile):
    def requirements( self):
        self.requires( "CL/ALIAS@user/testing")
"""
        export_alias("CM", cm)

        consumer = """from conan import ConanFile
class Pkg(ConanFile):
    def requirements( self):
        self.requires( "CM/ALIAS@user/testing")
        self.requires( "CL/ALIAS@user/testing")
        self.requires( "CK/ALIAS@user/testing")
        self.requires( "CH/ALIAS@user/testing")
"""
        client.save({"conanfile.py": consumer})
        client.run("info . --graph=file.dot")
        graphfile = client.load("file.dot")
        self.assertIn('"CM/0.1@user/testing" -> "CL/0.1@user/testing"', graphfile)
        self.assertIn('"CL/0.1@user/testing" -> "CK/0.1@user/testing"', graphfile)
        self.assertIn('"CL/0.1@user/testing" -> "CH/0.1@user/testing"', graphfile)
        self.assertIn('"CK/0.1@user/testing" -> "CH/0.1@user/testing"', graphfile)

    @parameterized.expand([(True, ), (False, )])
    def test_double_alias(self, use_requires):
        # https://github.com/conan-io/conan/issues/2583
        client = TestClient()
        if use_requires:
            conanfile = """from conan import ConanFile
class Pkg(ConanFile):
    requires = "%s"
"""
        else:
            conanfile = """from conan import ConanFile
class Pkg(ConanFile):
    def requirements(self):
        req = "%s"
        if req:
            self.requires(req)
"""

        client.save({"conanfile.py": conanfile % ""}, clean_first=True)
        client.run("export . --name=LibD --version=0.1 --user=user --channel=testing")
        client.alias("LibD/latest@user/testing",  "LibD/0.1@user/testing")

        client.save({"conanfile.py": conanfile % "LibD/latest@user/testing"})
        client.run("export . --name=LibC --version=0.1 --user=user --channel=testing")
        client.alias("LibC/latest@user/testing",  "LibC/0.1@user/testing")

        client.save({"conanfile.py": conanfile % "LibC/latest@user/testing"})
        client.run("export . --name=LibB --version=0.1 --user=user --channel=testing")
        client.alias("LibB/latest@user/testing",  "LibB/0.1@user/testing")

        client.save({"conanfile.py": conanfile % "LibC/latest@user/testing"})
        client.run("export . --name=LibA --version=0.1 --user=user --channel=testing")
        client.alias("LibA/latest@user/testing",  "LibA/0.1@user/testing")

        client.save(
                {"conanfile.txt": "[requires]\nLibA/latest@user/testing\nLibB/latest@user/testing"},
                clean_first=True)
        client.run("info conanfile.txt --graph=file.dot")
        graphfile = client.load("file.dot")
        self.assertIn('"LibA/0.1@user/testing" -> "LibC/0.1@user/testing"', graphfile)
        self.assertIn('"LibB/0.1@user/testing" -> "LibC/0.1@user/testing"', graphfile)
        self.assertIn('"LibC/0.1@user/testing" -> "LibD/0.1@user/testing"', graphfile)
        self.assertIn('"conanfile.txt" -> "LibB/0.1@user/testing"', graphfile)
        self.assertIn('"conanfile.txt" -> "LibA/0.1@user/testing"', graphfile)

    @parameterized.expand([(True, ), (False, )])
    def test_double_alias_options(self, use_requires):
        # https://github.com/conan-io/conan/issues/2583
        client = TestClient()
        if use_requires:
            conanfile = """from conan import ConanFile
class Pkg(ConanFile):
    requires = "%s"
    options = {"myoption": [True, False]}
    default_options = "myoption=True"
    def package_info(self):
        self.output.info("MYOPTION: {} {}".format(self.name, self.options.myoption))
"""
        else:
            conanfile = """from conan import ConanFile
class Pkg(ConanFile):
    options = {"myoption": [True, False]}
    default_options = "myoption=True"
    def configure(self):
        if self.name == "LibB":
            self.options["LibD"].myoption = False
    def requirements(self):
        req = "%s"
        if req:
            self.requires(req)
    def package_info(self):
        self.output.info("MYOPTION: {} {}".format(self.name, self.options.myoption))
"""

        client.save({"conanfile.py": conanfile % ""}, clean_first=True)
        client.run("export . --name=LibD --version=0.1 --user=user --channel=testing")
        client.alias("LibD/latest@user/testing",  "LibD/0.1@user/testing")

        client.save({"conanfile.py": conanfile % "LibD/latest@user/testing"})
        client.run("export . --name=LibC --version=0.1 --user=user --channel=testing")
        client.alias("LibC/latest@user/testing",  "LibC/0.1@user/testing")

        conanfile = conanfile % "LibC/latest@user/testing"
        conanfile = conanfile.replace('"myoption=True"', '"myoption=True", "LibD:myoption=False"')
        client.save({"conanfile.py": conanfile})

        client.run("export . --name=LibB --version=0.1 --user=user --channel=testing")
        client.alias("LibB/latest@user/testing",  "LibB/0.1@user/testing")

        client.save({"conanfile.py": conanfile % "LibC/latest@user/testing"})
        client.run("export . --name=LibA --version=0.1 --user=user --channel=testing")
        client.alias("LibA/latest@user/testing",  "LibA/0.1@user/testing")

        client.save({"conanfile.txt": "[requires]\nLibA/latest@user/testing\nLibB/latest@user/testing"},
                    clean_first=True)
        client.run("info conanfile.txt --graph=file.dot")
        graphfile = client.load("file.dot")
        self.assertIn('"LibA/0.1@user/testing" -> "LibC/0.1@user/testing"', graphfile)
        self.assertIn('"LibB/0.1@user/testing" -> "LibC/0.1@user/testing"', graphfile)
        self.assertIn('"LibC/0.1@user/testing" -> "LibD/0.1@user/testing"', graphfile)
        self.assertIn('"conanfile.txt" -> "LibB/0.1@user/testing"', graphfile)
        self.assertIn('"conanfile.txt" -> "LibA/0.1@user/testing"', graphfile)
        client.run("install conanfile.txt --build=missing")
        self.assertIn("LibD/0.1@user/testing: MYOPTION: LibD False", client.out)
        self.assertIn("LibB/0.1@user/testing: MYOPTION: LibB True", client.out)
        self.assertIn("LibA/0.1@user/testing: MYOPTION: LibA True", client.out)
        self.assertIn("LibC/0.1@user/testing: MYOPTION: LibC True", client.out)

    @parameterized.expand([(True, ), (False, )])
    def test_double_alias_ranges(self, use_requires):
        # https://github.com/conan-io/conan/issues/2583
        client = TestClient()
        if use_requires:
            conanfile = """from conan import ConanFile
class Pkg(ConanFile):
    requires = "%s"
"""
        else:
            conanfile = """from conan import ConanFile
class Pkg(ConanFile):
    def requirements(self):
        req = "%s"
        if req:
            self.requires(req)
"""

        client.save({"conanfile.py": conanfile % ""}, clean_first=True)
        client.run("export . --name=LibD --version=sha1 --user=user --channel=testing")
        client.alias("LibD/0.1@user/testing",  "LibD/sha1@user/testing")

        client.save({"conanfile.py": conanfile % "LibD/[~0.1]@user/testing"})
        client.run("export . --name=LibC --version=sha1 --user=user --channel=testing")
        client.alias("LibC/0.1@user/testing",  "LibC/sha1@user/testing")

        client.save({"conanfile.py": conanfile % "LibC/[~0.1]@user/testing"})
        client.run("export . --name=LibB --version=sha1 --user=user --channel=testing")
        client.alias("LibB/0.1@user/testing",  "LibB/sha1@user/testing")

        client.save({"conanfile.py": conanfile % "LibC/[~0.1]@user/testing"})
        client.run("export . --name=LibA --version=sha1 --user=user --channel=testing")
        client.alias("LibA/0.1@user/testing",  "LibA/sha1@user/testing")

        client.save({"conanfile.txt": "[requires]\nLibA/[~0.1]@user/testing\nLibB/[~0.1]@user/testing"},
                    clean_first=True)
        client.run("info conanfile.txt --graph=file.dot")
        graphfile = client.load("file.dot")
        self.assertIn('"LibA/sha1@user/testing" -> "LibC/sha1@user/testing"', graphfile)
        self.assertIn('"LibB/sha1@user/testing" -> "LibC/sha1@user/testing"', graphfile)
        self.assertIn('"LibC/sha1@user/testing" -> "LibD/sha1@user/testing"', graphfile)
        self.assertIn('"conanfile.txt" -> "LibB/sha1@user/testing"', graphfile)
        self.assertIn('"conanfile.txt" -> "LibA/sha1@user/testing"', graphfile)

    def test_basic(self):
        test_server = TestServer()
        servers = {"default": test_server}
        client = TestClient(servers=servers, inputs=["admin", "password"])
        for i in (1, 2):
            client.save({"conanfile.py": GenConanfile().with_name("hello").with_version("0.%s" % i)})
            client.run("export . --user=lasote --channel=channel")

        client.alias("hello/0.X@lasote/channel",  "hello/0.1@lasote/channel")
        conanfile_chat = textwrap.dedent("""
            from conan import ConanFile
            class TestConan(ConanFile):
                name = "Chat"
                version = "1.0"
                requires = "hello/0.X@lasote/channel"
                """)
        client.save({"conanfile.py": conanfile_chat}, clean_first=True)
        client.run("export . --user=lasote --channel=channel")
        client.save({"conanfile.txt": "[requires]\nChat/1.0@lasote/channel"}, clean_first=True)

        client.run("install . --build=missing")

        self.assertIn("hello/0.1@lasote/channel from local", client.out)
        self.assertNotIn("hello/0.X@lasote/channel", client.out)

        ref = RecipeReference.loads("Chat/1.0@lasote/channel")
        pkg_folder = client.cache.package_layout(ref).packages()
        folders = os.listdir(pkg_folder)
        pkg_folder = os.path.join(pkg_folder, folders[0])
        conaninfo = client.load(os.path.join(pkg_folder, "conaninfo.txt"))

        self.assertIn("hello/0.1@lasote/channel", conaninfo)
        self.assertNotIn("hello/0.X@lasote/channel", conaninfo)

        client.run('upload "*" --confirm -r default')
        client.run('remove "*" -c"')

        client.run("install .")
        self.assertIn("hello/0.1@lasote/channel from 'default'", client.out)
        self.assertNotIn("hello/0.X@lasote/channel from", client.out)

        client.alias("hello/0.X@lasote/channel",  "hello/0.2@lasote/channel")
        client.run("install . --build=missing")
        self.assertIn("hello/0.2", client.out)
        self.assertNotIn("hello/0.1", client.out)
