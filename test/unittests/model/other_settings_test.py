import os
import textwrap

from conan.internal.model.info import load_binary_info
from conan.api.model import RecipeReference
from conan.internal.paths import CONANFILE
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient
from conan.internal.util.files import load, save


class TestSettings:

    @staticmethod
    def _get_conaninfo(reference, client):
        ref = client.cache.get_latest_recipe_revision(RecipeReference.loads(reference))
        pkg_ids = client.cache.get_package_references(ref)
        pref = client.cache.get_latest_package_revision(pkg_ids[0])
        pkg_folder = client.cache.pkg_layout(pref).package()
        return load_binary_info(client.load(os.path.join(pkg_folder, "conaninfo.txt")))

    def test_wrong_settings(self):
        settings = textwrap.dedent("""\
            os:
                null:
                    subsystem: [null, msys]
            """)
        client = TestClient()
        save(client.paths.settings_path, settings)
        client.save_home({"profiles/default": ""})
        client.save({"conanfile.py": GenConanfile().with_settings("os", "compiler")})
        client.run("create . --name=pkg --version=0.1", assert_error=True)
        assert "ERROR: settings.yml: null setting can't have subsettings" in client.out

    def test_settings_constraint_error_type(self):
        # https://github.com/conan-io/conan/issues/3022
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Test(ConanFile):
                settings = "os"
                def build(self):
                    self.output.info("OS!!: %s" % self.settings.os)
            """)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("create . --name=pkg --version=0.1 --user=user --channel=testing -s os=Linux")
        assert "pkg/0.1@user/testing: OS!!: Linux" in client.out

    def test_settings_as_a_str(self):
        client = TestClient()
        client.save({CONANFILE: GenConanfile("say", "0.1").with_settings("os")})
        client.run("create . -s os=Windows --build missing")
        # Now read the conaninfo and verify that settings applied is only os and value is windows
        conan_info = self._get_conaninfo("say/0.1@", client)
        assert conan_info["settings"]["os"] == "Windows"

        client.run("remove say/0.1 -c")
        client.run("create . -s os=Linux --build missing")
        # Now read the conaninfo and verify that settings applied is only os and value is windows
        conan_info = self._get_conaninfo("say/0.1@", client)
        assert conan_info["settings"]["os"] == "Linux"

    def test_settings_as_a_list_conanfile(self):
        # Now with conanfile as a list
        client = TestClient()
        client.save({CONANFILE: GenConanfile("say", "0.1").with_settings("os", "arch")})
        client.run("create . -s os=Windows --build missing")
        conan_info = self._get_conaninfo("say/0.1@", client)
        assert conan_info["settings"]["os"] == "Windows"

    def test_settings_as_a_dict_conanfile(self):
        # Now with conanfile as a set
        content = textwrap.dedent("""
            from conan import ConanFile

            class SayConan(ConanFile):
                name = "say"
                version = "0.1"
                settings = {"os", "arch"}
            """)
        client = TestClient()
        client.save({CONANFILE: content})
        client.run("create . -s os=Windows --build missing")
        conan_info = self._get_conaninfo("say/0.1@", client)
        assert conan_info["settings"]["os"] == "Windows"

    def test_invalid_settings3(self):
        client = TestClient()
        # Test wrong settings in conanfile
        client.save({CONANFILE: GenConanfile().with_settings("invalid")})
        client.run("install . --build missing", assert_error=True)
        assert "'settings.invalid' doesn't exist" in client.out

        # Test wrong values in conanfile
    def test_invalid_settings4(self):
        client = TestClient()
        client.save({CONANFILE: GenConanfile("say", "0.1").with_settings("os")})
        client.run("create . -s os=ChromeOS --build missing", assert_error=True)
        assert "ERROR: Invalid setting 'ChromeOS' is not a valid 'settings.os' value." in client.out
        assert "Possible values are ['Windows', 'WindowsStore', 'WindowsCE', 'Linux'" in client.out

        # Now add new settings to config and try again
        config = load(client.paths.settings_path)
        config = config.replace("Windows:",
                                "Windows:\n    ChromeOS:\n")

        save(client.paths.settings_path, config)
        client.run("create . -s os=ChromeOS --build missing")

        # Settings is None
        content = textwrap.dedent("""
            from conan import ConanFile

            class SayConan(ConanFile):
                name = "say"
                version = "0.1"
                settings = None
            """)
        client.save({CONANFILE: content})
        client.run("remove say/0.1 -c")
        client.run("create . --build missing")
        conan_info = self._get_conaninfo("say/0.1", client)
        assert conan_info.get("settings") == None  # noqa

        # Settings is {}
        content = textwrap.dedent("""
            from conan import ConanFile

            class SayConan(ConanFile):
                name = "say"
                version = "0.1"
                settings = {}
            """)
        client.save({CONANFILE: content})
        client.run("remove say/0.1 -c")
        client.run("create . --build missing")
        conan_info = self._get_conaninfo("say/0.1", client)

        assert conan_info.get("settings") == None  # noqa
