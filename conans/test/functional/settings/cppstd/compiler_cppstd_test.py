# coding=utf-8

import os
import textwrap
import unittest

import pytest
from parameterized.parameterized import parameterized_class

from conans.client.tools import environment_append, save
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient


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
        with environment_append({"CONAN_DEFAULT_PROFILE_PATH": default_profile_path}):
            unittest.TestCase.run(self, *args, **kwargs)

    def setUp(self):
        self.t = TestClient(cache_folder=temp_folder())

        settings = ["os", "compiler", "build_type", "arch"]
        if self.recipe_cppstd:
            settings += ["cppstd"]

        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class Lib(ConanFile):
                settings = "{}"
            """.format('", "'.join(settings)))
        self.t.save({"conanfile.py": conanfile})

    def test_value_invalid(self):
        self.t.run("create . hh/0.1@user/channel -shh:compiler=apple-clang "
                   "-shh:compiler.cppstd=144", assert_error=True)
        self.assertIn("Invalid setting '144' is not a valid 'settings.compiler.cppstd' value",
                      self.t.out)

    def test_value_different_with_scoped_setting(self):
        self.t.run("create . hh/0.1@user/channel"
                   " -s hh:cppstd=11"
                   " -s hh:compiler=gcc"
                   " -s hh:compiler.cppstd=14", assert_error=True)
        self.assertIn("ERROR: Error in resulting settings for package 'hh': Do not use settings"
                      " 'compiler.cppstd' together with 'cppstd'", self.t.out)

    def test_value_different_with_general_setting(self):
        deprecation_number = 1 if self.recipe_cppstd else 0
        self.t.run("create . hh/0.1@user/channel"
                   " -s cppstd=17"
                   " -s hh:compiler=gcc"
                   " -s hh:compiler.cppstd=14", assert_error=True)
        self.assertIn("ERROR: Error in resulting settings for package 'hh': Do not use settings"
                      " 'compiler.cppstd' together with 'cppstd'", self.t.out)

    def test_conanfile_without_compiler(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class Lib(ConanFile):
                settings = "os", "arch"
        """)
        t = TestClient(cache_folder=temp_folder())
        t.save({'conanfile.py': conanfile})

        # No mismatch, because settings for this conanfile does not include `compiler`
        t.run("create . hh/0.1@user/channel"
              " -s cppstd=17"
              " -s hh:compiler=gcc"
              " -s hh:compiler.cppstd=14", assert_error=True)
        self.assertIn("ERROR: Error in resulting settings for package 'hh': Do not use settings"
                      " 'compiler.cppstd' together with 'cppstd'", t.out)

    def test_conanfile_without_compiler_but_cppstd(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class Lib(ConanFile):
                settings = "os", "arch", "cppstd"

                def configure(self):
                    self.output.info(">>> cppstd: {}".format(self.settings.cppstd))
        """)
        t = TestClient(cache_folder=temp_folder())
        t.save({'conanfile.py': conanfile}, clean_first=True)

        # No mismatch, because settings for this conanfile does not include `compiler`
        t.run("create . hh/0.1@user/channel"
              " -s cppstd=17"
              " -s hh:compiler=gcc"
              " -s hh:compiler.cppstd=14", assert_error=True)
        self.assertIn("ERROR: Error in resulting settings for package 'hh': Do not use settings"
                      " 'compiler.cppstd' together with 'cppstd'", t.out)


class UseCompilerCppStdSettingTests(unittest.TestCase):

    conanfile = textwrap.dedent("""
        from conans import ConanFile

        class Lib(ConanFile):
            settings = "cppstd", "os", "compiler", "arch", "build_type"

            def configure(self):
                self.output.info(">>> cppstd: {}".format(self.settings.cppstd))
                self.output.info(">>> compiler.cppstd: {}".format(self.settings.compiler.cppstd))
    """)

    def setUp(self):
        self.t = TestClient()
        self.t.save({'conanfile.py': self.conanfile})

    def test_only_cppstd(self):
        self.t.run("info . -s cppstd=14")
        self.assertNotIn(">>> compiler.cppstd: 14", self.t.out)
        self.assertIn(">>> cppstd: 14", self.t.out)
        self.assertIn(">>> compiler.cppstd: None", self.t.out)

    def test_only_compiler_cppstd(self):
        """ settings.cppstd is available only if declared explicitly (otherwise it is deprecated)
        """
        self.t.run("info . -s compiler.cppstd=14")
        self.assertNotIn(">>> cppstd: 14", self.t.out)
        self.assertIn(">>> cppstd: None", self.t.out)
        self.assertIn(">>> compiler.cppstd: 14", self.t.out)

    def test_both(self):
        settings_str = "-s cppstd=14 -s compiler.cppstd=14"
        self.t.run("info . {}".format(settings_str), assert_error=True)
        self.assertIn("Do not use settings 'compiler.cppstd' together with 'cppstd'."
                      " Use only the former one.", self.t.out)
