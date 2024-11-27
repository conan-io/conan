import json
import os
import re
import textwrap
import unittest

import pytest

from conan.cli.exit_codes import ERROR_INVALID_CONFIGURATION, ERROR_GENERAL
from conans.client.graph.graph import BINARY_INVALID
from conan.test.assets.genconanfile import GenConanfile
from conans.util.files import save
from conan.test.utils.tools import TestClient, NO_SETTINGS_PACKAGE_ID


class TestValidate(unittest.TestCase):

    def test_validate_create(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.errors import ConanInvalidConfiguration
            class Pkg(ConanFile):
                settings = "os"

                def validate(self):
                    if self.info.settings.os == "Windows":
                        raise ConanInvalidConfiguration("Windows not supported")
            """)

        client.save({"conanfile.py": conanfile})

        client.run("create . --name=pkg --version=0.1 -s os=Linux")
        self.assertIn("pkg/0.1: Package '9a4eb3c8701508aa9458b1a73d0633783ecc2270' created",
                      client.out)

        error = client.run("create . --name=pkg --version=0.1 -s os=Windows", assert_error=True)
        self.assertEqual(error, ERROR_INVALID_CONFIGURATION)
        self.assertIn("pkg/0.1: Invalid: Windows not supported", client.out)

        client.run("graph info --require pkg/0.1 -s os=Windows")
        self.assertIn("binary: Invalid", client.out)
        assert "info_invalid: Windows not supported" in client.out

        client.run("graph info --require pkg/0.1 -s os=Windows --format json")
        myjson = json.loads(client.stdout)
        self.assertEqual(myjson["graph"]["nodes"]["1"]["binary"], BINARY_INVALID)
        assert myjson["graph"]["nodes"]["1"]["info_invalid"] == "Windows not supported" in client.out

    def test_validate_header_only(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.errors import ConanInvalidConfiguration
            from conan.tools.build import check_min_cppstd
            class Pkg(ConanFile):
                settings = "os", "compiler"
                options = {"shared": [True, False], "header_only": [True, False],}
                default_options = {"shared": False, "header_only": True}

                def package_id(self):
                   if self.info.options.header_only:
                       self.info.clear()

                def validate(self):
                    if self.info.options.get_safe("header_only") == "False":
                        if self.info.settings.get_safe("compiler.version") == "12":
                          raise ConanInvalidConfiguration("This package cannot exist in gcc 12")
                        check_min_cppstd(self, 11)
                        # These configurations are impossible
                        if self.info.settings.os != "Windows" and self.info.options.shared:
                            raise ConanInvalidConfiguration("shared is only supported under windows")

                    # HOW CAN WE VALIDATE CPPSTD > 11 WHEN HEADER ONLY?

            """)

        client.save({"conanfile.py": conanfile})

        client.run("create . --name pkg --version=0.1 -s os=Linux -s compiler=gcc "
                   "-s compiler.version=11 -s compiler.libcxx=libstdc++11")
        assert re.search(r"Package '(.*)' created", str(client.out))

        client.run("create . --name pkg --version=0.1 -o header_only=False -s os=Linux "
                   "-s compiler=gcc -s compiler.version=12 -s compiler.libcxx=libstdc++11",
                   assert_error=True)

        assert "Invalid: This package cannot exist in gcc 12" in client.out

        client.run("create . --name pkg --version=0.1  -o header_only=False -s os=Macos "
                   "-s compiler=gcc -s compiler.version=11 -s compiler.libcxx=libstdc++11 "
                   "-s compiler.cppstd=98",
                   assert_error=True)

        assert "Invalid: Current cppstd (98) is lower than the required C++ " \
               "standard (11)" in client.out

        client.run("create . --name pkg --version=0.1  -o header_only=False -o shared=True "
                   "-s os=Macos -s compiler=gcc "
                   "-s compiler.version=11 -s compiler.libcxx=libstdc++11 -s compiler.cppstd=11",
                   assert_error=True)

        assert "Invalid: shared is only supported under windows" in client.out

    def test_validate_compatible(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.errors import ConanInvalidConfiguration
            class Pkg(ConanFile):
                settings = "os"

                def validate_build(self):
                    if self.settings.os == "Windows":
                        raise ConanInvalidConfiguration("Windows not supported")

                def compatibility(self):
                    if self.settings.os == "Windows":
                        return [{"settings": [("os", "Linux")]}]
            """)

        client.save({"conanfile.py": conanfile})

        client.run("create . --name=pkg --version=0.1 -s os=Linux")
        package_id = "9a4eb3c8701508aa9458b1a73d0633783ecc2270"
        missing_id = "ebec3dc6d7f6b907b3ada0c3d3cdc83613a2b715"
        self.assertIn(f"pkg/0.1: Package '{package_id}' created",
                      client.out)

        # This is the main difference, building from source for the specified conf, fails
        client.run("create . --name=pkg --version=0.1 -s os=Windows", assert_error=True)
        self.assertIn("pkg/0.1: Cannot build for this configuration: Windows not supported",
                      client.out)
        client.assert_listed_binary({"pkg/0.1": (missing_id, "Invalid")})

        client.run("install --requires=pkg/0.1@ -s os=Windows --build=pkg*", assert_error=True)
        self.assertIn("pkg/0.1: Cannot build for this configuration: Windows not supported",
                      client.out)
        self.assertIn("Windows not supported", client.out)

        client.run("install --requires=pkg/0.1@ -s os=Windows")
        self.assertIn(f"pkg/0.1: Main binary package '{missing_id}' missing", client.out)
        self.assertIn(f"Found compatible package '{package_id}'", client.out)
        client.assert_listed_binary({"pkg/0.1": (package_id, "Cache")})

        # --build=missing means "use existing binary if possible", and compatibles are valid binaries
        client.run("install --requires=pkg/0.1@ -s os=Windows --build=missing")
        self.assertIn(f"pkg/0.1: Main binary package '{missing_id}' missing", client.out)
        self.assertIn(f"Found compatible package '{package_id}'", client.out)
        client.assert_listed_binary({"pkg/0.1": (package_id, "Cache")})

        client.run("graph info --requires=pkg/0.1@ -s os=Windows")
        self.assertIn(f"pkg/0.1: Main binary package '{missing_id}' missing", client.out)
        self.assertIn(f"Found compatible package '{package_id}'", client.out)
        self.assertIn(f"package_id: {package_id}", client.out)

        client.run("graph info --requires=pkg/0.1@ -s os=Windows --build=pkg*")
        self.assertIn("binary: Invalid", client.out)

    def test_validate_remove_package_id_create(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
               from conan import ConanFile
               from conan.errors import ConanInvalidConfiguration
               class Pkg(ConanFile):
                   settings = "os"

                   def validate(self):
                       if self.info.settings.os == "Windows":
                           raise ConanInvalidConfiguration("Windows not supported")

                   def package_id(self):
                       del self.info.settings.os
               """)

        client.save({"conanfile.py": conanfile})

        client.run("create . --name=pkg --version=0.1 -s os=Linux")
        self.assertIn("pkg/0.1: Package '{}' created".format(NO_SETTINGS_PACKAGE_ID), client.out)

        client.run("create . --name=pkg --version=0.1 -s os=Windows", assert_error=True)
        self.assertIn("pkg/0.1: Invalid: Windows not supported", client.out)
        client.assert_listed_binary({"pkg/0.1": ("da39a3ee5e6b4b0d3255bfef95601890afd80709",
                                                 "Invalid")})

        client.run("graph info --requires=pkg/0.1@ -s os=Windows")
        self.assertIn("package_id: {}".format(NO_SETTINGS_PACKAGE_ID), client.out)

    def test_validate_compatible_also_invalid(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
           from conan import ConanFile
           from conan.errors import ConanInvalidConfiguration
           class Pkg(ConanFile):
               settings = "os", "build_type"

               def validate(self):
                   if self.info.settings.os == "Windows":
                       raise ConanInvalidConfiguration("Windows not supported")

               def compatibility(self):
                   if self.settings.build_type == "Debug" and self.settings.os != "Windows":
                       return [{"settings": [("build_type", "Release")]}]
               """)

        client.save({"conanfile.py": conanfile})

        client.run("create . --name=pkg --version=0.1 -s os=Linux -s build_type=Release")
        package_id = "c26ded3c7aa4408e7271e458d65421000e000711"
        client.assert_listed_binary({"pkg/0.1": (package_id, "Build")})
        # compatible_packges fallback works
        client.run("install --requires=pkg/0.1@ -s os=Linux -s build_type=Debug")
        client.assert_listed_binary({"pkg/0.1": (package_id, "Cache")})

        error = client.run("create . --name=pkg --version=0.1 -s os=Windows -s build_type=Release",
                           assert_error=True)

        self.assertEqual(error, ERROR_INVALID_CONFIGURATION)
        self.assertIn("pkg/0.1: Invalid: Windows not supported", client.out)

        client.run("graph info --requires=pkg/0.1@ -s os=Windows")
        assert "binary: Invalid" in client.out

    def test_validate_compatible_also_invalid_fail(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
           from conan import ConanFile
           from conan.errors import ConanInvalidConfiguration
           class Pkg(ConanFile):
               settings = "os", "build_type"

               def validate(self):
                   if self.info.settings.os == "Windows":
                       raise ConanInvalidConfiguration("Windows not supported")

               def compatibility(self):
                   if self.settings.build_type == "Debug":
                       return [{"settings": [("build_type", "Release")]}]
               """)

        client.save({"conanfile.py": conanfile})

        package_id = "c26ded3c7aa4408e7271e458d65421000e000711"
        client.run("create . --name=pkg --version=0.1 -s os=Linux -s build_type=Release")
        self.assertIn(f"pkg/0.1: Package '{package_id}' created",
                      client.out)
        # compatible_packges fallback works
        client.run("install --requires=pkg/0.1@ -s os=Linux -s build_type=Debug")
        client.assert_listed_binary({"pkg/0.1": (package_id, "Cache")})
        # Windows invalid configuration
        error = client.run("create . --name=pkg --version=0.1 -s os=Windows -s build_type=Release",
                           assert_error=True)
        self.assertEqual(error, ERROR_INVALID_CONFIGURATION)
        self.assertIn("pkg/0.1: Invalid: Windows not supported", client.out)

        error = client.run("install --requires=pkg/0.1@ -s os=Windows -s build_type=Release",
                           assert_error=True)
        self.assertEqual(error, ERROR_INVALID_CONFIGURATION)
        self.assertIn("pkg/0.1: Invalid: Windows not supported", client.out)

        # Windows missing binary: INVALID
        error = client.run("install --requires=pkg/0.1@ -s os=Windows -s build_type=Debug",
                           assert_error=True)
        self.assertEqual(error, ERROR_INVALID_CONFIGURATION)
        self.assertIn("pkg/0.1: Invalid: Windows not supported", client.out)

        error = client.run("create . --name=pkg --version=0.1 -s os=Windows -s build_type=Debug",
                           assert_error=True)
        self.assertEqual(error, ERROR_INVALID_CONFIGURATION)
        self.assertIn("pkg/0.1: Invalid: Windows not supported", client.out)

        # info
        client.run("graph info --requires=pkg/0.1@ -s os=Windows")
        assert "binary: Invalid" in client.out
        client.run("graph info --requires=pkg/0.1@ -s os=Windows -s build_type=Debug")
        assert "binary: Invalid" in client.out

    def test_validate_options(self):
        # The dependency option doesn't affect pkg package_id, so it could find a valid binary
        # in the cache. So ConanInvalidConfiguration will solve this issue.
        client = TestClient()
        client.save({"conanfile.py": GenConanfile().with_option("myoption", [1, 2, 3])
                                                   .with_default_option("myoption", 1)})
        client.run("create . --name=dep --version=0.1")
        client.run("create . --name=dep --version=0.1 -o dep/*:myoption=2")
        conanfile = textwrap.dedent("""
           from conan import ConanFile
           from conan.errors import ConanInvalidConfiguration
           class Pkg(ConanFile):
               requires = "dep/0.1"

               def validate(self):
                   if self.dependencies["dep"].options.myoption == 2:
                       raise ConanInvalidConfiguration("Option 2 of 'dep' not supported")
           """)

        client.save({"conanfile.py": conanfile})
        client.run("create . --name=pkg1 --version=0.1 -o dep/*:myoption=1")

        client.save({"conanfile.py": GenConanfile().with_requires("dep/0.1")
                                                   .with_default_option("dep/*:myoption", 2)})
        client.run("create . --name=pkg2 --version=0.1")

        client.save({"conanfile.py": GenConanfile().with_requires("pkg2/0.1", "pkg1/0.1")})
        error = client.run("install .", assert_error=True)
        self.assertEqual(error, ERROR_INVALID_CONFIGURATION)
        self.assertIn("pkg1/0.1: Invalid: Option 2 of 'dep' not supported", client.out)

    def test_validate_requires(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . --name=dep --version=0.1")
        client.run("create . --name=dep --version=0.2")
        conanfile = textwrap.dedent("""
           from conan import ConanFile
           from conan.errors import ConanInvalidConfiguration
           class Pkg(ConanFile):
               requires = "dep/0.1"

               def validate(self):
                   if self.dependencies["dep"].ref.version > "0.1":
                       raise ConanInvalidConfiguration("dep> 0.1 is not supported")
           """)

        client.save({"conanfile.py": conanfile})
        client.run("create . --name=pkg1 --version=0.1")

        client.save({"conanfile.py": GenConanfile()
                    .with_requirement("pkg1/0.1")
                    .with_requirement("dep/0.2", override=True)})
        error = client.run("install .", assert_error=True)
        self.assertEqual(error, ERROR_INVALID_CONFIGURATION)
        self.assertIn("pkg1/0.1: Invalid: dep> 0.1 is not supported", client.out)

        client.save({"conanfile.py": GenConanfile()
                    .with_requirement("pkg1/0.1")
                    .with_requirement("dep/0.2", force=True)})
        error = client.run("install .", assert_error=True)
        self.assertEqual(error, ERROR_INVALID_CONFIGURATION)
        self.assertIn("pkg1/0.1: Invalid: dep> 0.1 is not supported", client.out)

    def test_validate_package_id_mode(self):
        client = TestClient()
        save(client.cache.new_config_path, "core.package_id:default_unknown_mode=full_package_mode")
        conanfile = textwrap.dedent("""
          from conan import ConanFile
          from conan.errors import ConanInvalidConfiguration
          class Pkg(ConanFile):
              settings = "os"

              def validate(self):
                  if self.info.settings.os == "Windows":
                      raise ConanInvalidConfiguration("Windows not supported")
              """)
        client.save({"conanfile.py": conanfile})
        client.run("export . --name=dep --version=0.1")

        client.save({"conanfile.py": GenConanfile().with_requires("dep/0.1")})
        error = client.run("create . --name=pkg --version=0.1 -s os=Windows", assert_error=True)
        self.assertEqual(error, ERROR_INVALID_CONFIGURATION)
        client.assert_listed_binary({"dep/0.1": ("ebec3dc6d7f6b907b3ada0c3d3cdc83613a2b715",
                                                 "Invalid")})
        client.assert_listed_binary({"pkg/0.1": ("19ad5731bb09f24646c81060bd7730d6cb5b6108",
                                                 "Build")})
        self.assertIn("ERROR: There are invalid packages:", client.out)
        self.assertIn("dep/0.1: Invalid: Windows not supported", client.out)

    def test_validate_export_pkg(self):
        # https://github.com/conan-io/conan/issues/9797
        c = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.errors import ConanInvalidConfiguration

            class TestConan(ConanFile):
                def validate(self):
                    raise ConanInvalidConfiguration("never ever")
            """)
        c.save({"conanfile.py": conanfile})
        c.run("export-pkg . --name=test --version=1.0", assert_error=True)
        assert "ERROR: conanfile.py (test/1.0): Invalid ID: Invalid: never ever" in c.out

    def test_validate_build_export_pkg(self):
        # https://github.com/conan-io/conan/issues/9797
        c = TestClient()
        conanfile = textwrap.dedent("""
               from conan import ConanFile
               from conan.errors import ConanInvalidConfiguration

               class TestConan(ConanFile):
                   def validate_build(self):
                       raise ConanInvalidConfiguration("never ever")
               """)
        c.save({"conanfile.py": conanfile})
        c.run("export-pkg . --name=test --version=1.0", assert_error=True)
        assert "conanfile.py (test/1.0): Cannot build for this configuration: never ever" in c.out

    def test_validate_install(self):
        # https://github.com/conan-io/conan/issues/10602
        c = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.errors import ConanInvalidConfiguration

            class TestConan(ConanFile):
                def validate(self):
                    raise ConanInvalidConfiguration("never ever")
            """)
        c.save({"conanfile.py": conanfile})
        c.run("install .", assert_error=True)
        assert "ERROR: conanfile.py: Invalid ID: Invalid: never ever" in c.out


class TestValidateCppstd:
    """ aims to be a very close to real use case of cppstd management and validation in recipes
    """
    def test_build_17_consume_14(self):
        client = TestClient()
        # simplify it a bit
        compat = textwrap.dedent("""\
            def compatibility(conanfile):
                return [{"settings": [("compiler.cppstd", v)]} for v in ("11", "14", "17", "20")]
            """)
        save(os.path.join(client.cache.plugins_path, "compatibility/compatibility.py"), compat)
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.errors import ConanInvalidConfiguration
            class Pkg(ConanFile):
                name = "pkg"
                version = "0.1"
                settings = "compiler"

                def validate_build(self):
                    # Explicit logic instead of using check_min_cppstd that hides details
                    if int(str(self.settings.compiler.cppstd)) < 17:
                        raise ConanInvalidConfiguration("I need at least cppstd=17 to build")

                def validate(self):
                    if int(str(self.settings.compiler.cppstd)) < 14:
                        raise ConanInvalidConfiguration("I need at least cppstd=14 to be used")
            """)

        client.save({"conanfile.py": conanfile})

        settings = "-s compiler=gcc -s compiler.version=9 -s compiler.libcxx=libstdc++"
        client.run(f"create . {settings} -s compiler.cppstd=17")
        client.assert_listed_binary({"pkg/0.1": ("91faf062eb94767a31ff62a46767d3d5b41d1eff",
                                                 "Build")})
        # create with cppstd=14 fails, not enough
        client.run(f"create . {settings} -s compiler.cppstd=14", assert_error=True)
        client.assert_listed_binary({"pkg/0.1": ("36d978cbb4dc35906d0fd438732d5e17cd1e388d",
                                                 "Invalid")})
        assert "pkg/0.1: Cannot build for this configuration: I need at least cppstd=17 to build" \
               in client.out

        # Install with cppstd=14 can fallback to the previous one
        client.run(f"install --requires=pkg/0.1 {settings} -s compiler.cppstd=14")
        # 2 valid binaries, 17 and 20
        assert "pkg/0.1: Checking 2 compatible configurations" in client.out
        client.assert_listed_binary({"pkg/0.1": ("91faf062eb94767a31ff62a46767d3d5b41d1eff",
                                                 "Cache")})

        # install with not enough cppstd should fail
        client.run(f"install --requires=pkg/0.1@ {settings} -s compiler.cppstd=11",
                   assert_error=True)
        # not even trying to fallback to compatibles
        assert "pkg/0.1: Checking" not in client.out
        client.assert_listed_binary({"pkg/0.1": ("8415595b7485d90fc413c2f47298aa5fb05a5468",
                                                 "Invalid")})
        assert "I need at least cppstd=14 to be used" in client.out

    def test_header_only_14(self):
        client = TestClient()

        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.build import check_min_cppstd
            class Pkg(ConanFile):
                name = "pkg"
                version = "0.1"
                settings = "compiler"

                def package_id(self):
                    self.info.clear()

                def validate(self):
                    check_min_cppstd(self, 14)
            """)

        client.save({"conanfile.py": conanfile})

        settings = "-s compiler=gcc -s compiler.version=9 -s compiler.libcxx=libstdc++"
        client.run(f"create . {settings} -s compiler.cppstd=17")
        client.assert_listed_binary({"pkg/0.1": ("da39a3ee5e6b4b0d3255bfef95601890afd80709",
                                                 "Build")})
        client.run(f"create . {settings} -s compiler.cppstd=14")
        client.assert_listed_binary({"pkg/0.1": ("da39a3ee5e6b4b0d3255bfef95601890afd80709",
                                                 "Build")})

        client.run(f"create . {settings} -s compiler.cppstd=11", assert_error=True)
        client.assert_listed_binary({"pkg/0.1": ("da39a3ee5e6b4b0d3255bfef95601890afd80709",
                                                 "Invalid")})
        assert "Current cppstd (11) is lower than the required C++ standard (14)" in client.out

        # Install with cppstd=14 can fallback to the previous one
        client.run(f"install --requires=pkg/0.1 {settings} -s compiler.cppstd=14")
        client.assert_listed_binary({"pkg/0.1": ("da39a3ee5e6b4b0d3255bfef95601890afd80709",
                                                 "Cache")})

        # install with not enough cppstd should fail
        client.run(f"install --requires=pkg/0.1@ {settings} -s compiler.cppstd=11",
                   assert_error=True)
        # not even trying to fallback to compatibles
        assert "pkg/0.1: Checking" not in client.out
        client.assert_listed_binary({"pkg/0.1": ("da39a3ee5e6b4b0d3255bfef95601890afd80709",
                                                 "Invalid")})
        assert "Current cppstd (11) is lower than the required C++ standard (14)" in client.out

    def test_build_17_consume_14_transitive(self):
        """ what happens if we have:
        app->engine(shared-lib)->pkg(static-lib)
        if pkg is only buildable with cppstd>=17 and needs cppstd>=14 to be consumed, but
        as it is static it becomes an implementation detail of engine, that doesn't have any
        constraint or validate() at all
        """
        client = TestClient()
        # simplify it a bit
        compat = textwrap.dedent("""\
            def compatibility(conanfile):
                return [{"settings": [("compiler.cppstd", v)]} for v in ("11", "14", "17", "20")]
            """)
        save(os.path.join(client.cache.plugins_path, "compatibility/compatibility.py"), compat)
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.errors import ConanInvalidConfiguration
            class Pkg(ConanFile):
                name = "pkg"
                version = "0.1"
                settings = "compiler"
                package_type = "static-library"

                def validate_build(self):
                    # Explicit logic instead of using check_min_cppstd that hides details
                    if int(str(self.settings.compiler.cppstd)) < 17:
                        raise ConanInvalidConfiguration("I need at least cppstd=17 to build")

                def validate(self):
                    if int(str(self.settings.compiler.cppstd)) < 14:
                        raise ConanInvalidConfiguration("I need at least cppstd=14 to be used")
            """)
        engine = GenConanfile("engine", "0.1").with_package_type("shared-library") \
                                              .with_requires("pkg/0.1")
        app = GenConanfile("app", "0.1").with_package_type("application") \
                                        .with_requires("engine/0.1")
        client.save({"pkg/conanfile.py": conanfile,
                     "engine/conanfile.py": engine,
                     "app/conanfile.py": app})

        settings = "-s compiler=gcc -s compiler.version=9 -s compiler.libcxx=libstdc++"
        client.run(f"create pkg {settings} -s compiler.cppstd=17")
        client.assert_listed_binary({"pkg/0.1": ("91faf062eb94767a31ff62a46767d3d5b41d1eff",
                                                 "Build")})
        client.run(f"create engine {settings} -s compiler.cppstd=17")
        client.assert_listed_binary({"pkg/0.1": ("91faf062eb94767a31ff62a46767d3d5b41d1eff",
                                                 "Cache")})
        client.run(f"install app {settings} -s compiler.cppstd=17 -v")
        client.assert_listed_binary({"pkg/0.1": ("91faf062eb94767a31ff62a46767d3d5b41d1eff",
                                                 "Skip")})
        client.run(f"install app {settings} -s compiler.cppstd=14 -v")
        client.assert_listed_binary({"pkg/0.1": ("91faf062eb94767a31ff62a46767d3d5b41d1eff",
                                                 "Skip")})
        # No binary for engine exist for cppstd=11
        client.run(f"install app {settings} -s compiler.cppstd=11", assert_error=True)
        client.assert_listed_binary({"engine/0.1": ("dc24e2caf6e1fa3e8bb047ca0f5fa053c71df6db",
                                                    "Missing")})
        client.run(f"install app {settings} -s compiler.cppstd=11 --build=missing",
                   assert_error=True)
        assert 'pkg/0.1: Invalid: I need at least cppstd=14 to be used' in client.out

    def test_build_17_consume_14_transitive_erasure(self):
        """ The same as the above test:
        app->engine(shared-lib)->pkg(static-lib)
        but in this test, the engine shared-lib does "package_id()" erasure of "pkg" dependency,
        being able to reuse it then even when cppstd==11
        """
        client = TestClient()
        # simplify it a bit
        compat = textwrap.dedent("""\
            def compatibility(conanfile):
                return [{"settings": [("compiler.cppstd", v)]} for v in ("11", "14", "17", "20")]
            """)
        save(os.path.join(client.cache.plugins_path, "compatibility/compatibility.py"), compat)
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.errors import ConanInvalidConfiguration
            class Pkg(ConanFile):
                name = "pkg"
                version = "0.1"
                settings = "compiler"
                package_type = "static-library"

                def validate_build(self):
                    # Explicit logic instead of using check_min_cppstd that hides details
                    if int(str(self.settings.compiler.cppstd)) < 17:
                        raise ConanInvalidConfiguration("I need at least cppstd=17 to build")

                def validate(self):
                    if int(str(self.settings.compiler.cppstd)) < 14:
                        raise ConanInvalidConfiguration("I need at least cppstd=14 to be used")
            """)
        engine = textwrap.dedent("""
            from conan import ConanFile
            from conan.errors import ConanInvalidConfiguration
            class Pkg(ConanFile):
                name = "engine"
                version = "0.1"
                settings = "compiler"
                package_type = "shared-library"
                requires = "pkg/0.1"

                def package_id(self):
                    del self.info.settings.compiler.cppstd
                    self.info.requires["pkg"].full_version_mode()

            """)
        app = GenConanfile("app", "0.1").with_package_type("application") \
                                        .with_requires("engine/0.1")
        client.save({"pkg/conanfile.py": conanfile,
                     "engine/conanfile.py": engine,
                     "app/conanfile.py": app})

        settings = "-s compiler=gcc -s compiler.version=9 -s compiler.libcxx=libstdc++"
        client.run(f"create pkg {settings} -s compiler.cppstd=17")
        client.assert_listed_binary({"pkg/0.1": ("91faf062eb94767a31ff62a46767d3d5b41d1eff",
                                                 "Build")})
        client.run(f"create engine {settings} -s compiler.cppstd=17")
        client.assert_listed_binary({"engine/0.1": ("493976208e9989b554704f94f9e7b8e5ba39e5ab",
                                                    "Build")})
        client.assert_listed_binary({"pkg/0.1": ("91faf062eb94767a31ff62a46767d3d5b41d1eff",
                                                 "Cache")})
        client.run(f"install app {settings} -s compiler.cppstd=17 -v")
        client.assert_listed_binary({"engine/0.1": ("493976208e9989b554704f94f9e7b8e5ba39e5ab",
                                                    "Cache")})
        client.assert_listed_binary({"pkg/0.1": ("91faf062eb94767a31ff62a46767d3d5b41d1eff",
                                                 "Skip")})
        client.run(f"install app {settings} -s compiler.cppstd=14 -v")
        client.assert_listed_binary({"engine/0.1": ("493976208e9989b554704f94f9e7b8e5ba39e5ab",
                                                    "Cache")})
        client.assert_listed_binary({"pkg/0.1": ("91faf062eb94767a31ff62a46767d3d5b41d1eff",
                                                 "Skip")})
        # No binary for engine exist for cppstd=11
        client.run(f"install app {settings} -s compiler.cppstd=11 -v")
        client.assert_listed_binary({"pkg/0.1": ("8415595b7485d90fc413c2f47298aa5fb05a5468",
                                                 "Skip")})
        client.assert_listed_binary({"engine/0.1": ("493976208e9989b554704f94f9e7b8e5ba39e5ab",
                                                    "Cache")})
        client.run(f"install app {settings} -s compiler.cppstd=11 --build=engine*",
                   assert_error=True)
        assert 'pkg/0.1: Invalid: I need at least cppstd=14 to be used' in client.out

    @pytest.mark.parametrize("use_attribute", [True, False])
    def test_exact_cppstd(self, use_attribute):
        """ Using the default cppstd_compat sometimes is not desired, and a recipe can
        explicitly opt-out this default cppstd_compat behavior, if it knows its binaries
        won't be binary compatible among them for different cppstd values
        """
        client = TestClient()
        if use_attribute:
            conanfile = textwrap.dedent("""
                from conan import ConanFile
                class Pkg(ConanFile):
                    settings = "compiler"
                    extension_properties = {"compatibility_cppstd": False}
            """)
        else:
            conanfile = textwrap.dedent("""
                from conan import ConanFile
                class Pkg(ConanFile):
                    settings = "compiler"
                    def compatibility(self):
                        self.extension_properties = {"compatibility_cppstd": False}
            """)

        client.save({"conanfile.py": conanfile})

        settings = "-s compiler=gcc -s compiler.version=9 -s compiler.libcxx=libstdc++"
        client.run(f"create . --name=pkg --version=0.1 {settings} -s compiler.cppstd=17")
        client.assert_listed_binary({"pkg/0.1": ("91faf062eb94767a31ff62a46767d3d5b41d1eff",
                                                 "Build")})

        # Install with cppstd=14 can NOT fallback to the previous one
        client.run(f"install --requires=pkg/0.1 {settings} -s compiler.cppstd=14", assert_error=True)
        assert "ERROR: Missing prebuilt package for 'pkg/0.1'" in client.out
        assert "compiler.cppstd=14" in client.out
        assert "compiler.cppstd=17" not in client.out
        client.run(f"install --requires=pkg/0.1 {settings} -s compiler.cppstd=14 --build=missing")
        client.assert_listed_binary({"pkg/0.1": ("36d978cbb4dc35906d0fd438732d5e17cd1e388d",
                                                 "Build")})
        assert "compiler.cppstd=14" in client.out
        assert "compiler.cppstd=17" not in client.out


class TestCompatibleSettingsTarget(unittest.TestCase):
    """ aims to be a very close to real use case of tool being used across different settings_target
    """
    def test_settings_target_in_compatibility_method_within_recipe(self):
        client = TestClient()
        """
        test setting_target in recipe's compatibility method
        """
        tool_conanfile = textwrap.dedent("""
            from conan import ConanFile

            class Pkg(ConanFile):
                settings = "arch"
                def compatibility(self):
                    if self.settings_target.arch == "armv7":
                        return [{"settings_target": [("arch", "armv6")]}]

                def package_id(self):
                    self.info.settings_target = self.settings_target
                    for field in self.info.settings_target.fields:
                        if field != "arch":
                            self.info.settings_target.rm_safe(field)
            """)

        client.save({"conanfile.py": tool_conanfile})
        client.run("create . --name=tool --version=0.1 -s os=Linux -s:h arch=armv6 --build-require")
        package_id = client.created_package_id("tool/0.1")
        assert f"tool/0.1: Package '{package_id}' created" in client.out

        app_conanfile = textwrap.dedent("""
            from conan import ConanFile

            class Pkg(ConanFile):
                settings = "arch"
                def requirements(self):
                    self.tool_requires("tool/0.1")
            """)

        client.save({"conanfile.py": app_conanfile})
        client.run("create . --name=app --version=0.1 -s os=Linux -s:h arch=armv7")
        assert f"Found compatible package '{package_id}'" in client.out

    def test_settings_target_in_compatibility_in_global_compatibility_py(self):
        client = TestClient()
        """
        test setting_target in global compatibility method
        """
        compat = textwrap.dedent("""\
            def compatibility(self):
                if self.settings_target.arch == "armv7":
                    return [{"settings_target": [("arch", "armv6")]}]
            """)
        save(os.path.join(client.cache.plugins_path, "compatibility/compatibility.py"), compat)

        tool_conanfile = textwrap.dedent("""
            from conan import ConanFile

            class Pkg(ConanFile):
                settings = "arch"

                def package_id(self):
                    self.info.settings_target = self.settings_target
                    for field in self.info.settings_target.fields:
                        if field != "arch":
                            self.info.settings_target.rm_safe(field)
            """)

        client.save({"conanfile.py": tool_conanfile})
        client.run("create . --name=tool --version=0.1 -s os=Linux -s:h arch=armv6 --build-require")
        package_id = client.created_package_id("tool/0.1")

        assert f"tool/0.1: Package '{package_id}' created" in client.out

        app_conanfile = textwrap.dedent("""
            from conan import ConanFile

            class Pkg(ConanFile):
                settings = "arch"
                def requirements(self):
                    self.tool_requires("tool/0.1")
            """)

        client.save({"conanfile.py": app_conanfile})
        client.run("create . --name=app --version=0.1 -s os=Linux -s:h arch=armv7")
        assert f"Found compatible package '{package_id}'" in client.out

    def test_no_settings_target_in_recipe_but_in_compatibility_method(self):
        client = TestClient()
        """
        test settings_target in compatibility method when recipe is not a build-require
        this should not crash. When building down-stream package it should end up with
        ERROR_GENERAL instead of crash
        """

        tool_conanfile = textwrap.dedent("""
            from conan import ConanFile

            class Pkg(ConanFile):
                settings = "arch"
                def compatibility(self):
                    if self.settings_target.arch == "armv7":
                        return [{"settings_target": [("arch", "armv6")]}]
            """)

        client.save({"conanfile.py": tool_conanfile})
        client.run("create . --name=tool --version=0.1 -s os=Linux -s:h arch=armv6")
        package_id = client.created_package_id("tool/0.1")
        assert f"tool/0.1: Package '{package_id}' created" in client.out

        app_conanfile = textwrap.dedent("""
            from conan import ConanFile

            class Pkg(ConanFile):
                settings = "arch"
                def requirements(self):
                    self.tool_requires("tool/0.1")
            """)

        client.save({"conanfile.py": app_conanfile})
        error = client.run("create . --name=app --version=0.1 -s os=Linux -s:h arch=armv7", assert_error=True)
        self.assertEqual(error, ERROR_GENERAL)
        self.assertIn("ERROR: Missing prebuilt package for 'tool/0.1'", client.out)

    def test_no_settings_target_in_recipe_but_in_global_compatibility(self):
        client = TestClient()
        """
        test settings_target in global compatibility method when recipe is not a build-require
        this should not crash. When building down-stream package it should end up with
        ERROR_GENERAL instead of crash
        """
        compat = textwrap.dedent("""\
            def compatibility(self):
                if self.settings_target.arch == "armv7":
                    return [{"settings_target": [("arch", "armv6")]}]
            """)
        save(os.path.join(client.cache.plugins_path, "compatibility/compatibility.py"), compat)

        tool_conanfile = textwrap.dedent("""
            from conan import ConanFile

            class Pkg(ConanFile):
                settings = "arch"
            """)

        client.save({"conanfile.py": tool_conanfile})
        client.run("create . --name=tool --version=0.1 -s os=Linux -s:h arch=armv6")
        package_id = client.created_package_id("tool/0.1")
        assert f"tool/0.1: Package '{package_id}' created" in client.out

        app_conanfile = textwrap.dedent("""
            from conan import ConanFile

            class Pkg(ConanFile):
                settings = "arch"
                def requirements(self):
                    self.tool_requires("tool/0.1")
            """)

        client.save({"conanfile.py": app_conanfile})
        error = client.run("create . --name=app --version=0.1 -s os=Linux -s:h arch=armv7", assert_error=True)
        self.assertEqual(error, ERROR_GENERAL)
        self.assertIn("ERROR: Missing prebuilt package for 'tool/0.1'", client.out)

    def test_three_packages_with_and_without_settings_target(self):
        client = TestClient()
        """
        test 3 packages, tool_a and tool_b have a mutual downstream package (app), and when
        build app it should find tool_a (a compatible version of it), and find tool_b,
        and conan create should be successful.
        """
        compat = textwrap.dedent("""\
            def compatibility(self):
                if self.settings_target.arch == "armv7":
                    return [{"settings_target": [("arch", "armv6")]}]
            """)
        save(os.path.join(client.cache.plugins_path, "compatibility/compatibility.py"), compat)

        tool_a_conanfile = textwrap.dedent("""
            from conan import ConanFile

            class Pkg(ConanFile):
                settings = "arch"

                def package_id(self):
                    self.info.settings_target = self.settings_target
                    for field in self.info.settings_target.fields:
                        if field != "arch":
                            self.info.settings_target.rm_safe(field)
            """)

        client.save({"conanfile.py": tool_a_conanfile})
        client.run("create . --name=tool_a --version=0.1 -s os=Linux -s:h arch=armv6 -s:b arch=x86_64 --build-require")
        package_id_tool_a = client.created_package_id("tool_a/0.1")
        assert f"tool_a/0.1: Package '{package_id_tool_a}' created" in client.out

        tool_b_conanfile = textwrap.dedent("""
            from conan import ConanFile

            class Pkg(ConanFile):
                settings = "arch"
            """)

        client.save({"conanfile.py": tool_b_conanfile})
        client.run("create . --name=tool_b --version=0.1 -s os=Linux -s arch=x86_64 -s:b arch=x86_64")
        package_id_tool_b = client.created_package_id("tool_b/0.1")
        assert f"tool_b/0.1: Package '{package_id_tool_b}' created" in client.out

        app_conanfile = textwrap.dedent("""
            from conan import ConanFile

            class Pkg(ConanFile):
                settings = "arch"
                def requirements(self):
                    self.tool_requires("tool_a/0.1")
                    self.tool_requires("tool_b/0.1")
            """)

        client.save({"conanfile.py": app_conanfile})
        client.run("create . --name=app --version=0.1 -s os=Linux -s:h arch=armv7 -s:b arch=x86_64")
        assert f"Found compatible package '{package_id_tool_a}'" in client.out
        assert package_id_tool_b in client.out

    def test_settings_target_in_compatibility_method_within_recipe_package_info(self):
        # https://github.com/conan-io/conan/issues/14823
        client = TestClient()
        tool_conanfile = textwrap.dedent("""
            from conan import ConanFile

            class Pkg(ConanFile):
                settings = "arch"

                def compatibility(self):
                    return [{'settings': [('arch', 'armv6')]}]

                def package_info(self):
                    # This used to crash
                    self.settings_target.get_safe('compiler.link_time_optimization')
            """)

        client.save({"conanfile.py": tool_conanfile})
        client.run("create . --name=tool --version=0.1 -s os=Linux -s:b arch=armv6 --build-require")
        package_id = client.created_package_id("tool/0.1")
        assert f"tool/0.1: Package '{package_id}' created" in client.out

        client.run("install --tool-requires=tool/0.1 -s os=Linux -s:b arch=armv7")
        # This used to crash, not anymore
        assert f"Found compatible package '{package_id}'" in client.out
