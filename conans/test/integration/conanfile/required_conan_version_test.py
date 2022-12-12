import textwrap
import unittest

import mock

from conans import __version__
from conans.test.utils.tools import TestClient


class RequiredConanVersionTest(unittest.TestCase):

    def test_required_conan_version(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile

            required_conan_version = ">=100.0"

            class Lib(ConanFile):
                pass
            """)
        client.save({"conanfile.py": conanfile})
        client.run("export . --name=pkg --version=1.0", assert_error=True)
        self.assertIn("Current Conan version (%s) does not satisfy the defined one (>=100.0)"
                      % __version__, client.out)
        client.run("source . ", assert_error=True)
        self.assertIn("Current Conan version (%s) does not satisfy the defined one (>=100.0)"
                      % __version__, client.out)
        with mock.patch("conans.client.conf.required_version.client_version", "101.0"):
            client.run("export . --name=pkg --version=1.0")

        with mock.patch("conans.client.conf.required_version.client_version", "101.0-dev"):
            client.run("export . --name=pkg --version=1.0")

        client.run("install --requires=pkg/1.0@", assert_error=True)
        self.assertIn("Current Conan version (%s) does not satisfy the defined one (>=100.0)"
                      % __version__, client.out)

    def test_required_conan_version_with_loading_issues(self):
        # https://github.com/conan-io/conan/issues/11239
        client = TestClient()
        conanfile = textwrap.dedent("""
                    from conan import missing_import

                    required_conan_version = ">=100.0"

                    class Lib(ConanFile):
                        pass
                    """)
        client.save({"conanfile.py": conanfile})
        client.run("export . --name=pkg --version=1.0", assert_error=True)
        self.assertIn("Current Conan version (%s) does not satisfy the defined one (>=100.0)"
                      % __version__, client.out)

        # Assigning required_conan_version without spaces
        conanfile = textwrap.dedent("""
                            from conan import missing_import

                            required_conan_version=">=100.0"

                            class Lib(ConanFile):
                                pass
                            """)
        client.save({"conanfile.py": conanfile})
        client.run("export . --name=pkg --version=1.0", assert_error=True)
        self.assertIn("Current Conan version (%s) does not satisfy the defined one (>=100.0)"
                      % __version__, client.out)

        # If the range is correct, everything works, of course
        conanfile = textwrap.dedent("""
                            from conan import ConanFile

                            required_conan_version = ">1.0.0"

                            class Lib(ConanFile):
                                pass
                            """)
        client.save({"conanfile.py": conanfile})
        client.run("export . --name=pkg --version=1.0")

    def test_required_conan_version_invalid_syntax(self):
            """ required_conan_version used to warn of mismatching versions if spaces were present,
             but now we have a nicer error"""
            # https://github.com/conan-io/conan/issues/12692
            client = TestClient()
            conanfile = textwrap.dedent("""
            from conan import missing
            required_conan_version = ">= 1.0"
            class Lib(ConanFile):
                pass""")
            client.save({"conanfile.py": conanfile})
            client.run("export . --name=pkg --version=1.0", assert_error=True)
            self.assertNotIn(f"Current Conan version ({__version__}) does not satisfy the defined one "
                            "(>= 1.0)", client.out)
            self.assertIn("Error parsing version range >=", client.out)
