import os
import textwrap
import unittest

from conans.model.info import load_binary_info
from conans.model.recipe_ref import RecipeReference
from conan.internal.paths import CONANFILE
from conan.test.utils.tools import TestClient
from conans.util.files import load, save


class SettingsTest(unittest.TestCase):

    def _get_conaninfo(self, reference, client):
        ref = client.cache.get_latest_recipe_reference(RecipeReference.loads(reference))
        pkg_ids = client.cache.get_package_references(ref)
        pref = client.cache.get_latest_package_reference(pkg_ids[0])
        pkg_folder = client.cache.pkg_layout(pref).package()
        return load_binary_info(client.load(os.path.join(pkg_folder, "conaninfo.txt")))

    def test_wrong_settings(self):
        settings = """os:
    null:
        subsystem: [null, msys]
"""
        client = TestClient()
        save(client.cache.settings_path, settings)
        save(client.cache.default_profile_path, "")
        conanfile = """from conan import ConanFile
class Pkg(ConanFile):
    settings = "os", "compiler"
"""
        client.save({"conanfile.py": conanfile})
        client.run("create . --name=pkg --version=0.1 --user=lasote --channel=testing", assert_error=True)
        self.assertIn("ERROR: settings.yml: null setting can't have subsettings", client.out)

    def test_settings_constraint_error_type(self):
        # https://github.com/conan-io/conan/issues/3022
        conanfile = """from conan import ConanFile
class Test(ConanFile):
    settings = "os"
    def build(self):
        self.output.info("OS!!: %s" % self.settings.os)
    """
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("create . --name=pkg --version=0.1 --user=user --channel=testing -s os=Linux")
        self.assertIn("pkg/0.1@user/testing: OS!!: Linux", client.out)

    def test_settings_as_a_str(self):
        content = """
from conan import ConanFile

class SayConan(ConanFile):
    name = "say"
    version = "0.1"
    settings = "os"
"""
        client = TestClient()
        client.save({CONANFILE: content})
        client.run("create . -s os=Windows --build missing")
        # Now read the conaninfo and verify that settings applied is only os and value is windows
        conan_info = self._get_conaninfo("say/0.1@", client)
        self.assertEqual(conan_info["settings"]["os"], "Windows")

        client.run("remove say/0.1 -c")
        client.run("create . -s os=Linux --build missing")
        # Now read the conaninfo and verify that settings applied is only os and value is windows
        conan_info = self._get_conaninfo("say/0.1@", client)
        self.assertEqual(conan_info["settings"]["os"], "Linux")

    def test_settings_as_a_list_conanfile(self):
        # Now with conanfile as a list
        content = """
from conan import ConanFile

class SayConan(ConanFile):
    name = "say"
    version = "0.1"
    settings = "os", "arch"
"""
        client = TestClient()
        client.save({CONANFILE: content})
        client.run("create . -s os=Windows --build missing")
        conan_info = self._get_conaninfo("say/0.1@", client)
        self.assertEqual(conan_info["settings"]["os"], "Windows")

    def test_settings_as_a_dict_conanfile(self):
        # Now with conanfile as a dict
        # XXX: this test only works on machines w default arch "x86", "x86_64", "sparc" or "sparcv9"
        content = """
from conan import ConanFile

class SayConan(ConanFile):
    name = "say"
    version = "0.1"
    settings = {"os", "arch"}
"""
        client = TestClient()
        client.save({CONANFILE: content})
        client.run("create . -s os=Windows --build missing")
        conan_info = self._get_conaninfo("say/0.1@", client)
        self.assertEqual(conan_info["settings"]["os"], "Windows")

    def test_invalid_settings3(self):
        client = TestClient()

        # Test wrong settings in conanfile
        content = textwrap.dedent("""
            from conan import ConanFile

            class SayConan(ConanFile):
                settings = "invalid"
            """)

        client.save({CONANFILE: content})
        client.run("install . --build missing", assert_error=True)
        self.assertIn("'settings.invalid' doesn't exist", client.out)

        # Test wrong values in conanfile
    def test_invalid_settings4(self):
        content = """
from conan import ConanFile

class SayConan(ConanFile):
    name = "say"
    version = "0.1"
    settings = "os"
"""
        client = TestClient()
        client.save({CONANFILE: content})
        client.run("create . -s os=ChromeOS --build missing", assert_error=True)
        assert "ERROR: Invalid setting 'ChromeOS' is not a valid 'settings.os' value." in client.out
        assert "Possible values are ['Windows', 'WindowsStore', 'WindowsCE', 'Linux'" in client.out

        # Now add new settings to config and try again
        config = load(client.cache.settings_path)
        config = config.replace("Windows:",
                                "Windows:\n    ChromeOS:\n")

        save(client.cache.settings_path, config)
        client.run("create . -s os=ChromeOS --build missing")

        # Settings is None
        content = """
from conan import ConanFile

class SayConan(ConanFile):
    name = "say"
    version = "0.1"
    settings = None
"""
        client.save({CONANFILE: content})
        client.run("remove say/0.1 -c")
        client.run("create . --build missing")
        conan_info = self._get_conaninfo("say/0.1", client)
        self.assertEqual(conan_info.get("settings"), None)

        # Settings is {}
        content = """
from conan import ConanFile

class SayConan(ConanFile):
    name = "say"
    version = "0.1"
    settings = {}
"""
        client.save({CONANFILE: content})
        client.run("remove say/0.1 -c")
        client.run("create . --build missing")
        conan_info = self._get_conaninfo("say/0.1", client)

        self.assertEqual(conan_info.get("settings"), None)
