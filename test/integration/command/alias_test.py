import os
import textwrap
import unittest

from conans.model.recipe_ref import RecipeReference
from conan.test.utils.tools import TestClient, GenConanfile


class ConanAliasTest(unittest.TestCase):

    def test_repeated_alias(self):
        client = TestClient(light=True)
        client.alias("hello/0.x@lasote/channel",  "hello/0.1@lasote/channel")
        client.alias("hello/0.x@lasote/channel",  "hello/0.2@lasote/channel")
        client.alias("hello/0.x@lasote/channel",  "hello/0.3@lasote/channel")

    def test_basic(self):
        client = TestClient(light=True, default_server_user=True)
        for i in (1, 2):
            client.save({"conanfile.py": GenConanfile().with_name("hello").with_version("0.%s" % i)})
            client.run("export . --user=lasote --channel=channel")

        client.alias("hello/0.x@lasote/channel",  "hello/0.1@lasote/channel")
        conanfile_chat = textwrap.dedent("""
            from conan import ConanFile
            class TestConan(ConanFile):
                name = "chat"
                version = "1.0"
                requires = "hello/(0.x)@lasote/channel"
                """)
        client.save({"conanfile.py": conanfile_chat}, clean_first=True)
        client.run("export . --user=lasote --channel=channel")
        client.save({"conanfile.txt": "[requires]\nchat/1.0@lasote/channel"}, clean_first=True)

        client.run("install . --build=missing")
        assert "chat/1.0@lasote/channel: WARN: legacy: Requirement 'alias' is provided in Conan 2" in client.out

        client.assert_listed_require({"hello/0.1@lasote/channel": "Cache"})
        assert "hello/0.x@lasote/channel: hello/0.1@lasote/channel" in client.out

        ref = RecipeReference.loads("chat/1.0@lasote/channel")
        pref = client.get_latest_package_reference(ref)
        pkg_folder = client.get_latest_pkg_layout(pref).package()
        conaninfo = client.load(os.path.join(pkg_folder, "conaninfo.txt"))

        self.assertIn("hello/0.1", conaninfo)
        self.assertNotIn("hello/0.x", conaninfo)

        client.run('upload "*" --confirm -r default')
        client.run('remove "*" -c')

        client.run("install .")
        assert "'alias' is a Conan 1.X legacy feature" in client.out
        client.assert_listed_require({"hello/0.1@lasote/channel": "Downloaded (default)"})
        self.assertNotIn("hello/0.x@lasote/channel from", client.out)

        client.alias("hello/0.x@lasote/channel",  "hello/0.2@lasote/channel")
        client.run("install . --build=missing")
        self.assertIn("hello/0.2", client.out)
        self.assertNotIn("hello/0.1", client.out)

    def test_not_override_package(self):
        """ Do not override a package with an alias

            If we create an alias with the same name as an existing package, it will
            override the package without any warning.
        """
        t = TestClient(light=True)
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                description = "{}"
            """)

        # Create two packages
        reference1 = "pkga/0.1@user/testing"
        t.save({"conanfile.py": conanfile.format(reference1)})
        t.run("export . --name=pkga --version=0.1 --user=user --channel=testing")

        reference2 = "pkga/0.2@user/testing"
        t.save({"conanfile.py": conanfile.format(reference2)})
        t.run("export . --name=pkga --version=0.2 --user=user --channel=testing")
