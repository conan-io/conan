import platform
import textwrap

import pytest

from conan.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() != "Windows", reason="Only windows")
class TestConanSettingsPreprocessor:

    def test_runtime_auto(self):
        c = TestClient()
        # Ensure that compiler.runtime is now in the default Win MSVC profile
        default_profile = c.load_home("profiles/default")
        assert "compiler.runtime" in default_profile

        conanfile = textwrap.dedent("""\
            from conan import ConanFile

            class HelloConan(ConanFile):
                name = "hello0"
                version = "0.1"
                settings = "os", "compiler", "build_type"

                def configure(self):
                    self.output.info(f"Runtime_type: {self.settings.compiler.runtime_type}")
            """)

        c.save({"conanfile.py": conanfile})
        c.run("create .")
        assert "Runtime_type: Release" in c.out
        c.run("create . -s build_type=Debug")
        assert "Runtime_type: Debug" in c.out

    def test_runtime_not_present_ok(self):
        c = TestClient()
        c.save({"conanfile.txt": ""})
        c.run("install .")
        default_settings = c.load_home("settings.yml")
        default_settings = default_settings.replace("runtime:", "# runtime:")
        default_settings = default_settings.replace("runtime_type:", "# runtime_type:")
        profile = "[settings]\nos=Windows\ncompiler=msvc\ncompiler.version=191"
        c.save_home({"settings.yml": default_settings,
                     "profiles/default": profile})
        # Ensure the runtime setting is not there anymore
        c.run('install . -s compiler.runtime="dynamic"', assert_error=True)
        assert "'settings.compiler.runtime' doesn't exist for 'msvc'" in c.out

        # Now install, the preprocessor shouldn't fail nor do anything
        c.run("install .")
        assert "Installing packages" in c.out
