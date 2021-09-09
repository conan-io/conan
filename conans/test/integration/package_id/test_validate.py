import json
import textwrap
import unittest

import pytest

from conans.cli.exit_codes import ERROR_INVALID_CONFIGURATION
from conans.client.graph.graph import BINARY_INVALID
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient, NO_SETTINGS_PACKAGE_ID
from conans.util.files import save


class TestValidate(unittest.TestCase):

    def test_validate_create(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            from conans.errors import ConanInvalidConfiguration
            class Pkg(ConanFile):
                settings = "os"

                def validate(self):
                    if self.settings.os == "Windows":
                        raise ConanInvalidConfiguration("Windows not supported")
            """)

        client.save({"conanfile.py": conanfile})

        client.run("create . pkg/0.1@ -s os=Linux")
        self.assertIn("pkg/0.1: Package '9a4eb3c8701508aa9458b1a73d0633783ecc2270' created",
                      client.out)

        error = client.run("create . pkg/0.1@ -s os=Windows", assert_error=True)
        print(client.out)
        self.assertEqual(error, ERROR_INVALID_CONFIGURATION)
        self.assertIn("pkg/0.1: Invalid: Windows not supported", client.out)
        client.run("info pkg/0.1@ -s os=Windows")
        print(client.out)
        client.run("info pkg/0.1@ -s os=Windows --dry-build=missing")
        print(client.out)
        self.assertIn("ID: INVALID", client.out)
        client.run("info pkg/0.1@ -s os=Windows --json=myjson")
        myjson = json.loads(client.load("myjson"))
        self.assertEqual(myjson[0]["binary"], BINARY_INVALID)
        self.assertEqual(myjson[0]["id"], 'INVALID')

    def test_validate_compatible_create(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            from conans.errors import ConanInvalidConfiguration
            class Pkg(ConanFile):
                settings = "os"

                def validate(self):
                    if self.settings.os == "Windows":
                        raise ConanInvalidConfiguration("Windows not supported")

                def package_id(self):
                    if self.settings.os == "Windows":
                        compatible_pkg = self.info.clone()
                        compatible_pkg.settings.os = "Linux"
                        self.compatible_packages.append(compatible_pkg)
            """)

        client.save({"conanfile.py": conanfile})

        client.run("create . pkg/0.1@ -s os=Linux")
        self.assertIn("pkg/0.1: Package '02145fcd0a1e750fb6e1d2f119ecdf21d2adaac8' created",
                      client.out)

        client.run("create . pkg/0.1@ -s os=Windows", assert_error=True)
        self.assertIn("pkg/0.1: Invalid: Windows not supported", client.out)
        self.assertIn("pkg/0.1:INVALID - Invalid", client.out)
        client.run("info pkg/0.1@ -s os=Windows")
        self.assertIn("pkg/0.1: Main binary package 'cf2e4ff978548fafd099ad838f9ecb8858bf25cb' "
                      "missing. Using compatible package '02145fcd0a1e750fb6e1d2f119ecdf21d2adaac8'",
                      client.out)
        self.assertIn("ID: 02145fcd0a1e750fb6e1d2f119ecdf21d2adaac8", client.out)

    def test_validate_remove_package_id_create(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
               from conans import ConanFile
               from conans.errors import ConanInvalidConfiguration
               class Pkg(ConanFile):
                   settings = "os"

                   def validate(self):
                       if self.settings.os == "Windows":
                           raise ConanInvalidConfiguration("Windows not supported")

                   def package_id(self):
                       del self.info.settings.os
               """)

        client.save({"conanfile.py": conanfile})

        client.run("create . pkg/0.1@ -s os=Linux")
        self.assertIn("pkg/0.1: Package '{}' created".format(NO_SETTINGS_PACKAGE_ID), client.out)

        client.run("create . pkg/0.1@ -s os=Windows", assert_error=True)
        self.assertIn("pkg/0.1: Invalid: Windows not supported", client.out)
        self.assertIn("pkg/0.1:INVALID - Invalid", client.out)

        client.run("info pkg/0.1@ -s os=Windows")
        self.assertIn("ID: {}".format(NO_SETTINGS_PACKAGE_ID), client.out)

    def test_validate_compatible_also_invalid(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
           from conans import ConanFile
           from conans.errors import ConanInvalidConfiguration
           class Pkg(ConanFile):
               settings = "os", "build_type"

               def validate(self):
                   if self.settings.os == "Windows":
                       raise ConanInvalidConfiguration("Windows not supported")

               def package_id(self):
                   if self.settings.build_type == "Debug" and self.settings.os != "Windows":
                       compatible_pkg = self.info.clone()
                       compatible_pkg.settings.build_type = "Release"
                       self.compatible_packages.append(compatible_pkg)
               """)

        client.save({"conanfile.py": conanfile})

        client.run("create . pkg/0.1@ -s os=Linux -s build_type=Release")
        self.assertIn("pkg/0.1: Package 'c26ded3c7aa4408e7271e458d65421000e000711' created",
                      client.out)
        # compatible_packges fallback works
        client.run("install pkg/0.1@ -s os=Linux -s build_type=Debug")
        self.assertIn("pkg/0.1:c26ded3c7aa4408e7271e458d65421000e000711 - Cache", client.out)

        error = client.run("create . pkg/0.1@ -s os=Windows -s build_type=Release",
                           assert_error=True)
        self.assertEqual(error, ERROR_INVALID_CONFIGURATION)
        self.assertIn("pkg/0.1: Invalid: Windows not supported", client.out)

        client.run("info pkg/0.1@ -s os=Windows")
        self.assertIn("ID: INVALID", client.out)

    def test_validate_compatible_also_invalid_fail(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
           from conans import ConanFile
           from conans.errors import ConanInvalidConfiguration
           class Pkg(ConanFile):
               settings = "os", "build_type"

               def validate(self):
                   if self.settings.os == "Windows":
                       raise ConanInvalidConfiguration("Windows not supported")

               def package_id(self):
                   if self.settings.build_type == "Debug":
                       compatible_pkg = self.info.clone()
                       compatible_pkg.settings.build_type = "Release"
                       self.compatible_packages.append(compatible_pkg)
               """)

        client.save({"conanfile.py": conanfile})

        package_id = "c26ded3c7aa4408e7271e458d65421000e000711"
        client.run("create . pkg/0.1@ -s os=Linux -s build_type=Release")
        self.assertIn(f"pkg/0.1: Package '{package_id}' created",
                      client.out)
        # compatible_packges fallback works
        client.run("install pkg/0.1@ -s os=Linux -s build_type=Debug")
        self.assertIn(f"pkg/0.1:{package_id} - Cache", client.out)

        # Windows invalid configuration
        error = client.run("create . pkg/0.1@ -s os=Windows -s build_type=Release",
                           assert_error=True)
        self.assertEqual(error, ERROR_INVALID_CONFIGURATION)
        self.assertIn("pkg/0.1: Invalid: Windows not supported", client.out)

        error = client.run("install pkg/0.1@ -s os=Windows -s build_type=Release",
                           assert_error=True)
        self.assertEqual(error, ERROR_INVALID_CONFIGURATION)
        self.assertIn("pkg/0.1: Invalid: Windows not supported", client.out)

        # Windows missing binary: INVALID
        error = client.run("install pkg/0.1@ -s os=Windows -s build_type=Debug",
                           assert_error=True)
        self.assertEqual(error, ERROR_INVALID_CONFIGURATION)
        self.assertIn("pkg/0.1: Invalid: Windows not supported", client.out)

        error = client.run("create . pkg/0.1@ -s os=Windows -s build_type=Debug",
                           assert_error=True)
        self.assertEqual(error, ERROR_INVALID_CONFIGURATION)
        self.assertIn("pkg/0.1: Invalid: Windows not supported", client.out)

        # info
        client.run("info pkg/0.1@ -s os=Windows")
        self.assertIn("ID: INVALID", client.out)
        client.run("info pkg/0.1@ -s os=Windows -s build_type=Debug")
        self.assertIn("ID: INVALID", client.out)

    @pytest.mark.xfail(reason="The way to check options of transitive deps has changed")
    def test_validate_options(self):
        # The dependency option doesn't affect pkg package_id, so it could find a valid binary
        # in the cache. So ConanErrorConfiguration will solve this issue.
        client = TestClient()
        client.save({"conanfile.py": GenConanfile().with_option("myoption", [1, 2, 3])
                                                   .with_default_option("myoption", 1)})
        client.run("create . dep/0.1@")
        client.run("create . dep/0.1@ -o dep:myoption=2")
        conanfile = textwrap.dedent("""
           from conans import ConanFile
           from conans.errors import ConanErrorConfiguration
           class Pkg(ConanFile):
               requires = "dep/0.1"

               def validate(self):
                   if self.options["dep"].myoption == 2:
                       raise ConanErrorConfiguration("Option 2 of 'dep' not supported")
           """)

        client.save({"conanfile.py": conanfile})
        client.run("create . pkg1/0.1@ -o dep:myoption=1")

        client.save({"conanfile.py": GenConanfile().with_requires("dep/0.1")
                                                   .with_default_option("dep:myoption", 2)})
        client.run("create . pkg2/0.1@")

        client.save({"conanfile.py": GenConanfile().with_requires("pkg1/0.1", "pkg2/0.1")})
        error = client.run("install .", assert_error=True)
        print(client.out)
        self.assertEqual(error, ERROR_INVALID_CONFIGURATION)
        self.assertIn("pkg1/0.1: ConfigurationError: Option 2 of 'dep' not supported", client.out)

    @pytest.mark.xfail(reason="The way to check versions of transitive deps has changed")
    def test_validate_requires(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . dep/0.1@")
        client.run("create . dep/0.2@")
        conanfile = textwrap.dedent("""
           from conans import ConanFile
           from conans.errors import ConanInvalidConfiguration
           class Pkg(ConanFile):
               requires = "dep/0.1"

               def validate(self):
                   # FIXME: This is a ugly interface DO NOT MAKE IT PUBLIC
                   # if self.info.requires["dep"].full_version ==
                   if self.requires["dep"].ref.version > "0.1":
                       raise ConanInvalidConfiguration("dep> 0.1 is not supported")
           """)

        client.save({"conanfile.py": conanfile})
        client.run("create . pkg1/0.1@")

        client.save({"conanfile.py": GenConanfile().with_requires("pkg1/0.1", "dep/0.2")})
        error = client.run("install .", assert_error=True)
        self.assertEqual(error, ERROR_INVALID_CONFIGURATION)
        self.assertIn("pkg1/0.1: Invalid: dep> 0.1 is not supported", client.out)

    def test_validate_package_id_mode(self):
        client = TestClient()
        # client.run("config set general.default_package_id_mode=full_package_mode")
        save(client.cache.new_config_path, "core.package_id:default_mode=full_package_mode")
        conanfile = textwrap.dedent("""
          from conans import ConanFile
          from conans.errors import ConanInvalidConfiguration
          class Pkg(ConanFile):
              settings = "os"

              def validate(self):
                  if self.settings.os == "Windows":
                      raise ConanInvalidConfiguration("Windows not supported")
              """)
        client.save({"conanfile.py": conanfile})
        client.run("export . dep/0.1@")

        client.save({"conanfile.py": GenConanfile().with_requires("dep/0.1")})
        error = client.run("create . pkg/0.1@ -s os=Windows", assert_error=True)

        self.assertEqual(error, ERROR_INVALID_CONFIGURATION)
        self.assertIn("dep/0.1:INVALID - Invalid", client.out)
        self.assertIn("pkg/0.1:INVALID - Invalid", client.out)
        self.assertIn("ERROR: There are invalid packages (packages that cannot "
                      "exist for this configuration):", client.out)
        self.assertIn("dep/0.1: Invalid: Windows not supported", client.out)
        self.assertIn("pkg/0.1: Invalid: Invalid transitive dependencies", client.out)
