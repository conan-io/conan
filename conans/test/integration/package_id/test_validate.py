import json
import re
import textwrap
import unittest

from conans.cli.exit_codes import ERROR_INVALID_CONFIGURATION
from conans.client.graph.graph import BINARY_INVALID
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


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
        self.assertIn("pkg/0.1: Package 'cb054d0b3e1ca595dc66bc2339d40f1f8f04ab31' created",
                      client.out)

        error = client.run("create . pkg/0.1@ -s os=Windows", assert_error=True)
        self.assertEqual(error, ERROR_INVALID_CONFIGURATION)
        self.assertIn("pkg/0.1: Invalid ID: Windows not supported", client.out)
        client.run("info pkg/0.1@ -s os=Windows")
        self.assertIn("ID: INVALID", client.out)
        client.run("info pkg/0.1@ -s os=Windows --json=myjson")
        myjson = json.loads(client.load("myjson"))
        self.assertEqual(myjson[0]["binary"], BINARY_INVALID)
        self.assertEqual(myjson[0]["id"], 'INVALID')

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

        client.run("create . pkg/0.1@ -s os=Linux -s compiler=gcc "
                   "-s compiler.version=11 -s compiler.libcxx=libstdc++11")
        assert re.search(r"Package '(.*)' created", str(client.out))

        client.run("create . pkg/0.1@ -o header_only=False -s os=Linux -s compiler=gcc "
                   "-s compiler.version=12 -s compiler.libcxx=libstdc++11", assert_error=True)

        assert "Invalid ID: This package cannot exist in gcc 12" in client.out

        client.run("create . pkg/0.1@ -o header_only=False -s os=Macos -s compiler=gcc "
                   "-s compiler.version=11 -s compiler.libcxx=libstdc++11 -s compiler.cppstd=98",
                   assert_error=True)

        assert "Invalid ID: Current cppstd (98) is lower than the required C++ " \
               "standard (11)" in client.out

        client.run("create . pkg/0.1@ -o header_only=False -o shared=True "
                   "-s os=Macos -s compiler=gcc "
                   "-s compiler.version=11 -s compiler.libcxx=libstdc++11 -s compiler.cppstd=11",
                   assert_error=True)

        assert "Invalid ID: shared is only supported under windows" in client.out

    def test_validate_compatible(self):
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
        self.assertIn("pkg/0.1: Package 'cb054d0b3e1ca595dc66bc2339d40f1f8f04ab31' created",
                      client.out)

        # This is the main difference, building from source for the specified conf, fails
        client.run("create . pkg/0.1@ -s os=Windows", assert_error=True)
        self.assertIn("pkg/0.1:INVALID - Invalid", client.out)
        self.assertIn("Windows not supported", client.out)

        client.run("install pkg/0.1@ -s os=Windows --build=pkg", assert_error=True)
        self.assertIn("pkg/0.1:INVALID - Invalid", client.out)
        self.assertIn("Windows not supported", client.out)

        client.run("install pkg/0.1@ -s os=Windows")
        self.assertIn("pkg/0.1: Main binary package 'INVALID' missing. "
                      "Using compatible package 'cb054d0b3e1ca595dc66bc2339d40f1f8f04ab31'",
                      client.out)
        self.assertIn("pkg/0.1:cb054d0b3e1ca595dc66bc2339d40f1f8f04ab31 - Cache", client.out)

        # --build=missing means "use existing binary if possible", and compatibles are valid binaries
        client.run("install pkg/0.1@ -s os=Windows --build=missing")
        self.assertIn("pkg/0.1: Main binary package 'INVALID' missing. "
                      "Using compatible package 'cb054d0b3e1ca595dc66bc2339d40f1f8f04ab31'",
                      client.out)
        self.assertIn("pkg/0.1:cb054d0b3e1ca595dc66bc2339d40f1f8f04ab31 - Cache", client.out)

        client.run("info pkg/0.1@ -s os=Windows")
        self.assertIn("pkg/0.1: Main binary package 'INVALID' missing. "
                      "Using compatible package 'cb054d0b3e1ca595dc66bc2339d40f1f8f04ab31'",
                      client.out)
        self.assertIn("ID: cb054d0b3e1ca595dc66bc2339d40f1f8f04ab31", client.out)

        client.run("info pkg/0.1@ -s os=Windows --dry-build=pkg")
        self.assertIn("Binary: Invalid", client.out)

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
        self.assertIn("pkg/0.1: Package '24c3aa2d6c5929d53bd86b31e020c55d96b265c7' created",
                      client.out)
        # compatible_packges fallback works
        client.run("install pkg/0.1@ -s os=Linux -s build_type=Debug")
        self.assertIn("pkg/0.1:24c3aa2d6c5929d53bd86b31e020c55d96b265c7 - Cache", client.out)

        error = client.run("create . pkg/0.1@ -s os=Windows -s build_type=Release",
                           assert_error=True)
        self.assertEqual(error, ERROR_INVALID_CONFIGURATION)
        self.assertIn("pkg/0.1: Invalid ID: Windows not supported", client.out)

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

        client.run("create . pkg/0.1@ -s os=Linux -s build_type=Release")
        self.assertIn("pkg/0.1: Package '24c3aa2d6c5929d53bd86b31e020c55d96b265c7' created",
                      client.out)
        # compatible_packges fallback works
        client.run("install pkg/0.1@ -s os=Linux -s build_type=Debug")
        self.assertIn("pkg/0.1:24c3aa2d6c5929d53bd86b31e020c55d96b265c7 - Cache", client.out)

        # Windows invalid configuration
        error = client.run("create . pkg/0.1@ -s os=Windows -s build_type=Release",
                           assert_error=True)
        self.assertEqual(error, ERROR_INVALID_CONFIGURATION)
        self.assertIn("pkg/0.1: Invalid ID: Windows not supported", client.out)

        error = client.run("install pkg/0.1@ -s os=Windows -s build_type=Release",
                           assert_error=True)
        self.assertEqual(error, ERROR_INVALID_CONFIGURATION)
        self.assertIn("pkg/0.1: Invalid ID: Windows not supported", client.out)

        # Windows missing binary: INVALID
        error = client.run("install pkg/0.1@ -s os=Windows -s build_type=Debug",
                           assert_error=True)
        self.assertEqual(error, ERROR_INVALID_CONFIGURATION)
        self.assertIn("pkg/0.1: Invalid ID: Windows not supported", client.out)

        error = client.run("create . pkg/0.1@ -s os=Windows -s build_type=Debug",
                           assert_error=True)
        self.assertEqual(error, ERROR_INVALID_CONFIGURATION)
        self.assertIn("pkg/0.1: Invalid ID: Windows not supported", client.out)

        # info
        client.run("info pkg/0.1@ -s os=Windows")
        self.assertIn("ID: INVALID", client.out)
        client.run("info pkg/0.1@ -s os=Windows -s build_type=Debug")
        self.assertIn("ID: INVALID", client.out)

    def test_validate_options(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile().with_option("myoption", [1, 2, 3])
                                                   .with_default_option("myoption", 1)})
        client.run("create . dep/0.1@")
        client.run("create . dep/0.1@ -o dep:myoption=2")
        conanfile = textwrap.dedent("""
           from conans import ConanFile
           from conans.errors import ConanInvalidConfiguration
           class Pkg(ConanFile):
               requires = "dep/0.1"

               def validate(self):
                   if self.options["dep"].myoption == 2:
                       raise ConanInvalidConfiguration("Option 2 of 'dep' not supported")
           """)

        client.save({"conanfile.py": conanfile})
        client.run("create . pkg1/0.1@ -o dep:myoption=1")

        client.save({"conanfile.py": GenConanfile().with_requires("dep/0.1")
                                                   .with_default_option("dep:myoption", 2)})
        client.run("create . pkg2/0.1@")

        client.save({"conanfile.py": GenConanfile().with_requires("pkg1/0.1", "pkg2/0.1")})
        error = client.run("install .", assert_error=True)
        self.assertEqual(error, ERROR_INVALID_CONFIGURATION)
        self.assertIn("pkg1/0.1: Invalid ID: Option 2 of 'dep' not supported", client.out)

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
        self.assertIn("pkg1/0.1: Invalid ID: dep> 0.1 is not supported", client.out)

    def test_validate_package_id_mode(self):
        client = TestClient()
        client.run("config set general.default_package_id_mode=full_package_mode")
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
        self.assertIn("dep/0.1: Invalid ID: Windows not supported", client.out)
        self.assertIn("pkg/0.1: Invalid ID: Invalid transitive dependencies", client.out)

    def test_validate_export_pkg(self):
        # https://github.com/conan-io/conan/issues/9797
        c = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            from conans.errors import ConanInvalidConfiguration

            class TestConan(ConanFile):
                def validate(self):
                    raise ConanInvalidConfiguration("never ever")
            """)
        c.save({"conanfile.py": conanfile})
        c.run("export-pkg . test/1.0@", assert_error=True)
        assert "Invalid ID: never ever" in c.out

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
        c.run("install .")
        assert "conanfile.py: ERROR: Invalid ID: never ever" in c.out
        assert "Trying to install dependencies, but this configuration will fail to build a package"\
               in c.out


class TestValidateCppstd:
    """ aims to be a very close to real use case of cppstd management and validation in recipes
    """
    def test_build_17_consume_14(self):
        client = TestClient()
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

                def compatibility(conanfile):
                    return [{"settings": [("compiler.cppstd", v)]} for v in ("11", "14", "17", "20")]
            """)

        client.save({"conanfile.py": conanfile})

        settings = "-s compiler=gcc -s compiler.version=9 -s compiler.libcxx=libstdc++"
        client.run(f"create . {settings} -s compiler.cppstd=17")
        assert "pkg/0.1:7558a15eea8c5762fa0602874a38dde9d36229c1 - Build" in client.out

        # create with cppstd=14 fails, not enough
        client.run(f"create . {settings} -s compiler.cppstd=14", assert_error=True)
        assert "pkg/0.1:e480cd97ef8f9dfdc31a7c0710c26d9b8d78375a - Invalid" in client.out
        assert "pkg/0.1: Cannot build for this configuration: I need at least cppstd=17 to build" \
               in client.out

        # Install with cppstd=14 can fallback to the previous one
        client.run(f"install pkg/0.1@ {settings} -s compiler.cppstd=14")
        assert "Using compatible package '7558a15eea8c5762fa0602874a38dde9d36229c1'" in client.out
        assert "pkg/0.1:7558a15eea8c5762fa0602874a38dde9d36229c1 - Cache" in client.out

        # FIXME 2.0: install with not enough cppstd should fail, but it doesnt
        # It is important to know that this only happens with "compatible_packages", otherwise
        # it will also fail (ConanCenter)
        client.run(f"install pkg/0.1@ {settings} -s compiler.cppstd=11")
        # not even trying to fallback to compatibles
        assert "Using compatible package '7558a15eea8c5762fa0602874a38dde9d36229c1'" in client.out
        assert "pkg/0.1:7558a15eea8c5762fa0602874a38dde9d36229c1 - Cache" in client.out
