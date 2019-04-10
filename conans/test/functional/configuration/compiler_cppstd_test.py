# coding=utf-8

import textwrap
import unittest

from parameterized import parameterized
from parameterized.parameterized import parameterized_class

from conans.test.utils.deprecation import catch_deprecation_warning
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient


@parameterized_class([{"recipe_cppstd": True}, {"recipe_cppstd": False}, ])
class SettingsCppStdScopedPackageTests(unittest.TestCase):
    # Validation of scoped settings is delayed until graph computation, a conanfile can
    #   declare a different set of settings, so we should wait until then to validate it.

    def setUp(self):
        self.tmp_folder = temp_folder()
        self.t = TestClient(base_folder=self.tmp_folder)

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
        self.t.run("create . hh/0.1@user/channel -shh:compiler=apple-clang -shh:compiler.cppstd=144",
                   assert_error=True)
        self.assertIn("Invalid setting '144' is not a valid 'settings.compiler.cppstd' value",
                      self.t.out)

    def test_value_different_with_scoped_setting(self):
        deprecation_number = 1 if self.recipe_cppstd else 0
        with catch_deprecation_warning(self, n=deprecation_number):
            self.t.run("create . hh/0.1@user/channel"
                       " -s hh:cppstd=11"
                       " -s hh:compiler=apple-clang"
                       " -s hh:compiler.version=10.0"
                       " -s hh:compiler.libcxx=libc++"
                       " -s hh:compiler.cppstd=14", assert_error=self.recipe_cppstd)
        if self.recipe_cppstd:
            self.assertIn("Package 'hh/0.1@user/channel': The specified 'compiler.cppstd=14' and"
                          " 'cppstd=11' are different", self.t.out)

    def test_value_different_with_general_setting(self):
        deprecation_number = 2 if self.recipe_cppstd else 0
        with catch_deprecation_warning(self, n=deprecation_number):
            self.t.run("create . hh/0.1@user/channel"
                       " -s cppstd=17"
                       " -s hh:compiler=apple-clang"
                       " -s hh:compiler.version=10.0"
                       " -s hh:compiler.libcxx=libc++"
                       " -s hh:compiler.cppstd=14", assert_error=self.recipe_cppstd)
        if self.recipe_cppstd:
            self.assertIn("Package 'hh/0.1@user/channel': The specified 'compiler.cppstd=14' and"
                          " 'cppstd=17' are different", self.t.out)

    def test_conanfile_without_compiler(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class Lib(ConanFile):
                settings = "os", "arch"
        """)
        t = TestClient(base_folder=temp_folder())
        t.save({'conanfile.py': conanfile})

        with catch_deprecation_warning(self):
            # No mismatch, because settings for this conanfile does not include `compiler`
            t.run("create . hh/0.1@user/channel"
                  " -s cppstd=17"
                  " -s hh:compiler=apple-clang"
                  " -s hh:compiler.cppstd=14")

    def test_conanfile_without_compiler_but_cppstd(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class Lib(ConanFile):
                settings = "os", "arch", "cppstd"
                
                def configure(self):
                    self.output.info(">>> cppstd: {}".format(self.settings.cppstd))
        """)
        t = TestClient(base_folder=temp_folder())
        t.save({'conanfile.py': conanfile}, clean_first=True)

        with catch_deprecation_warning(self, n=2):
            # No mismatch, because settings for this conanfile does not include `compiler`
            t.run("create . hh/0.1@user/channel"
                  " -s cppstd=17"
                  " -s hh:compiler=apple-clang"
                  " -s hh:compiler.cppstd=14")
        self.assertIn("Setting 'cppstd' is deprecated in favor of 'compiler.cppstd'", t.out)
        self.assertIn(">>> cppstd: 17", t.out)


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

    def test_user_notice(self):
        self.t.run("info .")
        self.assertIn("Setting 'cppstd' is deprecated in favor of 'compiler.cppstd',"
                      " please update your recipe.", self.t.out)

    @parameterized.expand([(True, ), (False, )])
    def test_use_cppstd(self, compiler_setting):
        settings_str = "-s cppstd=14 -s compiler.cppstd=14" if compiler_setting else "-s cppstd=14"
        with catch_deprecation_warning(self, n=2):
            self.t.run("info . {}".format(settings_str))
        self.assertIn(">>> cppstd: 14", self.t.out)
        self.assertIn(">>> compiler.cppstd: 14", self.t.out)

    def test_only_compiler_cppstd(self):
        """ settings.cppstd is available only if declared explicitly (otherwise it is deprecated) """
        self.t.run("info . -s compiler.cppstd=14")
        self.assertNotIn(">>> cppstd: 14", self.t.out)
        self.assertIn(">>> cppstd: None", self.t.out)
        self.assertIn(">>> compiler.cppstd: 14", self.t.out)
