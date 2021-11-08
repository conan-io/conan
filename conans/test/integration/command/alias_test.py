import os
import textwrap
import unittest


from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient, GenConanfile


class ConanAliasTest(unittest.TestCase):

    def test_alias_different_name(self):
        client = TestClient()
        client.run("alias myalias/1.0@user/channel lib/1.0@user/channel", assert_error=True)
        self.assertIn("An alias can only be defined to a package with the same name",
                      client.out)

    def test_repeated_alias(self):
        client = TestClient()
        client.run("alias Hello/0.X@lasote/channel Hello/0.1@lasote/channel")
        client.run("alias Hello/0.X@lasote/channel Hello/0.2@lasote/channel")
        client.run("alias Hello/0.X@lasote/channel Hello/0.3@lasote/channel")

    def test_existing_python_requires(self):
        # https://github.com/conan-io/conan/issues/8702
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . test-python-requires/0.1@user/testing")
        client.save({"conanfile.py": """from conans import ConanFile
class Pkg(ConanFile):
    python_requires = 'test-python-requires/0.1@user/testing'"""})
        client.run("create . pkg/0.1@user/testing")
        client.run("alias pkg/0.1@user/testing Pkg/0.2@user/testing", assert_error=True)
        self.assertIn("ERROR: Reference 'pkg/0.1@user/testing' is already a package",
                      client.out)

    def test_basic(self):
        client = TestClient(default_server_user=True)
        for i in (1, 2):
            client.save({"conanfile.py": GenConanfile().with_name("hello").with_version("0.%s" % i)})
            client.run("export . lasote/channel")

        client.run("alias Hello/0.X@lasote/channel Hello/0.1@lasote/channel")
        conanfile_chat = textwrap.dedent("""
            from conans import ConanFile
            class TestConan(ConanFile):
                name = "Chat"
                version = "1.0"
                requires = "Hello/(0.X)@lasote/channel"
                """)
        client.save({"conanfile.py": conanfile_chat}, clean_first=True)
        client.run("export . lasote/channel")
        client.save({"conanfile.txt": "[requires]\nChat/1.0@lasote/channel"}, clean_first=True)

        client.run("install . --build=missing")

        self.assertIn("Hello/0.1@lasote/channel from local", client.out)
        self.assertNotIn("Hello/0.X@lasote/channel", client.out)

        ref = ConanFileReference.loads("Chat/1.0@lasote/channel")
        pref = client.get_latest_prev(ref)
        pkg_folder = client.get_latest_pkg_layout(pref).package()
        conaninfo = client.load(os.path.join(pkg_folder, "conaninfo.txt"))

        self.assertIn("Hello/0.1", conaninfo)
        self.assertNotIn("Hello/0.X", conaninfo)

        client.run('upload "*" --all --confirm -r default')
        client.run('remove "*" -f')

        client.run("install .")
        self.assertIn("Hello/0.1@lasote/channel from 'default'", client.out)
        self.assertNotIn("Hello/0.X@lasote/channel from", client.out)

        client.run("alias Hello/0.X@lasote/channel Hello/0.2@lasote/channel")
        client.run("install . --build=missing")
        self.assertIn("Hello/0.2", client.out)
        self.assertNotIn("Hello/0.1", client.out)

    def test_not_override_package(self):
        """ Do not override a package with an alias

            If we create an alias with the same name as an existing package, it will
            override the package without any warning.
        """
        t = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                description = "{}"
            """)

        # Create two packages
        reference1 = "pkga/0.1@user/testing"
        t.save({"conanfile.py": conanfile.format(reference1)})
        t.run("export . {}".format(reference1))

        reference2 = "PkgA/0.2@user/testing"
        t.save({"conanfile.py": conanfile.format(reference2)})
        t.run("export . {}".format(reference2))

        # Now create an alias overriding one of them
        alias = reference2
        t.run("alias {alias} {reference}".format(alias=alias, reference=reference1),
              assert_error=True)
        self.assertIn("ERROR: Reference '{}' is already a package".format(alias), t.out)

        # Check that the package is not damaged
        t.run("inspect {} -a description".format(reference2))
        self.assertIn("description: {}".format(reference2), t.out)

        # Remove it, and create the alias again (twice, override an alias is allowed)
        t.run("remove {} -f".format(reference2))
        t.run("alias {alias} {reference}".format(alias=alias, reference=reference1))
        t.run("alias {alias} {reference}".format(alias=alias, reference=reference1))

        t.run("inspect {} -a description".format(reference2))
        self.assertIn("description: None", t.out)  # The alias conanfile doesn't have description
