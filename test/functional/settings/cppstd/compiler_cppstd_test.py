import os
import textwrap
import unittest

from parameterized.parameterized import parameterized_class

from conan.test.utils.env import environment_update
from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient
from conans.util.files import save


@parameterized_class([{"recipe_cppstd": True}, {"recipe_cppstd": False}, ])
class SettingsCppStdScopedPackageTests(unittest.TestCase):
    # Validation of scoped settings is delayed until graph computation, a conanfile can
    #   declare a different set of settings, so we should wait until then to validate it.

    default_profile = textwrap.dedent("""
        [settings]
        os=Linux
        arch=x86
        compiler=gcc
        compiler.version=7
        compiler.libcxx=libstdc++11
    """)

    def run(self, *args, **kwargs):
        default_profile_path = os.path.join(temp_folder(), "default.profile")
        save(default_profile_path, self.default_profile)
        with environment_update({"CONAN_DEFAULT_PROFILE_PATH": default_profile_path}):
            unittest.TestCase.run(self, *args, **kwargs)

    def setUp(self):
        self.t = TestClient(cache_folder=temp_folder())

        settings = ["os", "compiler", "build_type", "arch"]
        if self.recipe_cppstd:
            settings += ["cppstd"]

        conanfile = textwrap.dedent("""
            from conan import ConanFile

            class Lib(ConanFile):
                settings = "{}"
            """.format('", "'.join(settings)))
        self.t.save({"conanfile.py": conanfile})

    def test_value_invalid(self):
        self.t.run("create . --name=hh --version=0.1 --user=user --channel=channel -shh*:compiler=apple-clang "
                   "-shh*:compiler.cppstd=144", assert_error=True)
        self.assertIn("Invalid setting '144' is not a valid 'settings.compiler.cppstd' value",
                      self.t.out)
