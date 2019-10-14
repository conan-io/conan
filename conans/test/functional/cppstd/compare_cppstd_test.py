import os
import textwrap
import unittest

from conans.client.tools import environment_append, save
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient


class SettingsCppStdCompareTests(unittest.TestCase):
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
        self.tmp_folder = temp_folder()
        self.client = TestClient(base_folder=self.tmp_folder)

    def test_compiler_cppstd_compare(self):
        conanfile = textwrap.dedent("""
                    from conans import ConanFile

                    class CppstdLib(ConanFile):
                        settings = "compiler"

                        def configure(self):
                            assert self.settings.compiler.cppstd > 'gnu11'
                            self.output.info("cppstd okay")
                    """)

        # validate greater than
        self.client.save({"conanfile.py": conanfile})
        self.client.run("create . foo/0.1@user/channel -s compiler.cppstd=14")
        self.assertIn("foo/0.1@user/channel: cppstd okay", self.client.out)

        self.client.save({"conanfile.py": conanfile})
        self.client.run("create . foo/0.1@user/channel -s compiler.cppstd=gnu14")
        self.assertIn("foo/0.1@user/channel: cppstd okay", self.client.out)

        conanfile = conanfile.replace("gnu11", "20")
        self.client.save({"conanfile.py": conanfile})
        self.client.run("create . foo/0.1@user/channel -s compiler.cppstd=14", assert_error=True)
        self.assertIn("assert self.settings.compiler.cppstd > '20'", self.client.out)

        # validate equals
        conanfile = conanfile.replace("> '20'", "== 'gnu11'")
        self.client.save({"conanfile.py": conanfile})
        self.client.run("create . foo/0.1@user/channel -s compiler.cppstd=gnu11")
        self.assertIn("foo/0.1@user/channel: cppstd okay", self.client.out)

        self.client.save({"conanfile.py": conanfile})
        self.client.run("create . foo/0.1@user/channel -s compiler.cppstd=11")
        self.assertIn("foo/0.1@user/channel: cppstd okay", self.client.out)

        self.client.save({"conanfile.py": conanfile})
        self.client.run("create . foo/0.1@user/channel -s compiler.cppstd=14", assert_error=True)
        self.assertIn("assert self.settings.compiler.cppstd == 'gnu11'", self.client.out)

        # validate less
        conanfile = conanfile.replace("== 'gnu11'", "< '14'")
        self.client.save({"conanfile.py": conanfile})
        self.client.run("create . foo/0.1@user/channel -s compiler.cppstd=11")
        self.assertIn("foo/0.1@user/channel: cppstd okay", self.client.out)

        self.client.run("create . foo/0.1@user/channel -s compiler.cppstd=gnu11")
        self.assertIn("foo/0.1@user/channel: cppstd okay", self.client.out)

        self.client.run("create . foo/0.1@user/channel -s compiler.cppstd=17", assert_error=True)
        self.assertIn("assert self.settings.compiler.cppstd < '14'", self.client.out)
