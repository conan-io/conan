import os
import textwrap
import unittest

from parameterized import parameterized

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient, NO_SETTINGS_PACKAGE_ID
from conans.util.files import mkdir


class SetVersionNameTest(unittest.TestCase):

    @parameterized.expand([("", ), ("@user/channel", )])
    def test_set_version_name(self, user_channel):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Lib(ConanFile):
                def set_name(self):
                    self.name = "pkg"
                def set_version(self):
                    self.version = "2.1"
            """)
        client.save({"conanfile.py": conanfile})
        user_channel_arg = "--user=user --channel=channel" if user_channel else ""
        client.run("export . %s" % user_channel_arg)
        self.assertIn("pkg/2.1%s: Exported" % user_channel,
                      client.out)
        # installing it doesn't break
        client.run("install --requires=pkg/2.1%s --build=missing" % (user_channel or "@"))
        client.assert_listed_require({f"pkg/2.1{user_channel}": "Cache"})
        client.assert_listed_binary({f"pkg/2.1{user_channel}": (NO_SETTINGS_PACKAGE_ID, "Build")})

        client.run("install --requires=pkg/2.1%s --build=missing" % (user_channel or "@"))
        client.assert_listed_require({f"pkg/2.1{user_channel}": "Cache"})
        client.assert_listed_binary({f"pkg/2.1{user_channel}": (NO_SETTINGS_PACKAGE_ID, "Cache")})

        # Local flow should also work
        client.run("install .")
        self.assertIn("conanfile.py (pkg/2.1):", client.out)

    def test_set_version_name_file(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.files import load
            class Lib(ConanFile):
                def set_name(self):
                    self.name = load(self, "name.txt")
                def set_version(self):
                    self.version = load(self, "version.txt")
            """)
        client.save({"conanfile.py": conanfile,
                     "name.txt": "pkg",
                     "version.txt": "2.1"})
        client.run("export . --user=user --channel=testing")
        self.assertIn("pkg/2.1@user/testing: Exported", client.out)
        client.run("install --requires=pkg/2.1@user/testing --build=missing")
        client.assert_listed_binary({f"pkg/2.1@user/testing": (NO_SETTINGS_PACKAGE_ID, "Build")})
        client.run("install --requires=pkg/2.1@user/testing")
        client.assert_listed_binary({f"pkg/2.1@user/testing": (NO_SETTINGS_PACKAGE_ID, "Cache")})
        # Local flow should also work
        client.run("install .")
        self.assertIn("conanfile.py (pkg/2.1):", client.out)

    def test_set_version_name_errors(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Lib(ConanFile):
                def set_name(self):
                    self.name = "pkg"
                def set_version(self):
                    self.version = "2.1"
            """)
        client.save({"conanfile.py": conanfile})
        client.run("export . --name=other --version=1.1 --user=user --channel=testing")
        self.assertIn("pkg/2.1@user/testing", client.out)
        client.run("export .  --version=1.1 --user=user --channel=testing")
        self.assertIn("pkg/2.1@user/testing", client.out)
        # These are checked but match and don't conflict
        client.run("export . --version=2.1 --user=user --channel=testing")
        client.run("export . --name=pkg --version=2.1 --user=user --channel=testing")

        # Local flow should also fail
        client.run("install . --name=other --version=1.2")
        self.assertIn("", client.out)

    def test_set_version_name_appending(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
               from conan import ConanFile
               class Lib(ConanFile):
                   def set_name(self):
                       self.name = self.name + ".extra"
                   def set_version(self):
                       self.version = self.version + ".extra"
               """)
        client.save({"conanfile.py": conanfile})
        client.run("export . --name=pkg --version=1.0")
        self.assertIn("pkg.extra/1.0.extra: Exported", client.out)

    def test_set_version_name_only_not_cli(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Lib(ConanFile):
                def set_name(self):
                    self.name = self.name or "pkg"
                def set_version(self):
                    self.version = self.version or "2.0"
            """)
        client.save({"conanfile.py": conanfile})
        client.run("export . --name=other --version=1.1 --user=user --channel=testing")
        self.assertIn("other/1.1@user/testing: Exported", client.out)
        client.run("export .  --version=1.1 --user=user --channel=testing")
        self.assertIn("pkg/1.1@user/testing: Exported", client.out)
        client.run("export . --user=user --channel=testing")
        self.assertIn("pkg/2.0@user/testing: Exported", client.out)

        # Local flow should also work
        client.run("install . --name=other --version=1.2")
        self.assertIn("conanfile.py (other/1.2)", client.out)
        client.run("install .")
        self.assertIn("conanfile.py (pkg/2.0)", client.out)

    def test_set_version_name_crash(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Lib(ConanFile):
                def set_name(self):
                    self.name = error
            """)
        client.save({"conanfile.py": conanfile})
        client.run("export .", assert_error=True)
        self.assertIn("ERROR: conanfile.py: Error in set_name() method, line 5", client.out)
        self.assertIn("name 'error' is not defined", client.out)
        conanfile = textwrap.dedent("""
           from conan import ConanFile
           class Lib(ConanFile):
               def set_version(self):
                   self.version = error
           """)
        client.save({"conanfile.py": conanfile})
        client.run("export .", assert_error=True)
        self.assertIn("ERROR: conanfile.py: Error in set_version() method, line 5", client.out)
        self.assertIn("name 'error' is not defined", client.out)

    def test_set_version_cwd(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            import os
            from conan import ConanFile
            from conan.tools.files import load
            class Lib(ConanFile):
                name = "pkg"
                def set_version(self):
                    self.version = load(self, "version.txt")
            """)
        client.save({"conanfile.py": conanfile})
        mkdir(os.path.join(client.current_folder, "build"))
        with client.chdir("build"):
            client.save({"version.txt": "2.1"}, clean_first=True)
            client.run("export .. ")
            self.assertIn("pkg/2.1: Exported", client.out)


def test_set_version_forbidden_chars():
    c = TestClient()
    c.save({"conanfile.py": GenConanfile("pkg", "$$$")})
    c.run("export .", assert_error=True)
    assert "ERROR: Invalid package version '$$$'" in c.out

    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Lib(ConanFile):
            name = "pkg"
            def set_version(self):
                self.version = "$$$"
        """)
    c.save({"conanfile.py": conanfile})
    c.run("export .", assert_error=True)
    assert "ERROR: Invalid package version '$$$'" in c.out


def test_set_version_carriage_return():
    c = TestClient()
    c.save({"conanfile.py": GenConanfile("pkg", r"1.0\n")})
    c.run("export .", assert_error=True)
    assert "ERROR: Invalid package version '1.0" in c.out

    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import load
        class Lib(ConanFile):
            name = "pkg"
            def set_version(self):
                self.version = load(self, "version.txt")
        """)
    c.save({"conanfile.py": conanfile,
            "version.txt": "1.0\n"})
    c.run("export .", assert_error=True)
    assert "ERROR: Invalid package version '1.0" in c.out


def test_set_version_channel():
    """
    Dynamically setting the user and channel is possible with the ``set_version()``
    not recommended, but possible.
    """
    c = TestClient()

    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import load
        class Lib(ConanFile):
            name = "pkg"
            version = "0.1"
            def set_version(self):
                self.user = "myuser"
                self.channel = "mychannel"
        """)
    c.save({"conanfile.py": conanfile})
    c.run("export .")
    assert "pkg/0.1@myuser/mychannel: Exported" in c.out
