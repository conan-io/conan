import platform
import pytest

from conan.test.utils.tools import TestClient
from conan.internal.util.files import load, save


@pytest.mark.skipif(platform.system() != "Windows", reason="Only windows")
class TestConanSettingsPreprocessor:

    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = TestClient()
        self.conanfile = '''
from conan import ConanFile

class HelloConan(ConanFile):
    name = "hello0"
    version = "0.1"
    settings = "os", "compiler", "build_type"

    def configure(self):
        self.output.warning("Runtime_type: %s" % self.settings.get_safe("compiler.runtime_type"))
        '''
        self.client.save({"conanfile.py": self.conanfile})

        self.client.run("export . --user=lasote --channel=channel")

    def test_runtime_auto(self):
        # Ensure that compiler.runtime is not declared
        default_profile = self.client.load_home("profiles/default")
        assert "compiler.runtime" not in default_profile
        self.client.run("install --requires=hello0/0.1@lasote/channel --build missing")
        assert "Runtime_type: Release" in self.client.out
        self.client.run("install --requires=hello0/0.1@lasote/channel --build missing -s build_type=Debug")
        assert "Runtime_type: Debug" in self.client.out

    def test_runtime_not_present_ok(self):
        self.client.run("install .")
        default_settings = load(self.client.paths.settings_path)
        default_settings = default_settings.replace("runtime:", "# runtime:")
        default_settings = default_settings.replace("runtime_type:", "# runtime_type:")
        save(self.client.paths.settings_path, default_settings)
        self.client.save_home({
            "profiles/default": "[settings]\nos=Windows\ncompiler=msvc\ncompiler.version=191"
        })
        # Ensure the runtime setting is not there anymore
        self.client.run('install --requires=hello0/0.1@lasote/channel --build missing '
                        '-s compiler.runtime="dynamic"', assert_error=True)
        assert "'settings.compiler.runtime' doesn't exist for 'msvc'" in self.client.out

        # Now install, the preprocessor shouldn't fail nor do anything
        self.client.run("install --requires=hello0/0.1@lasote/channel --build missing")
        assert "Installing packages" in self.client.out
