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

    def test_commented_out_required_conan_version(self):
        """Used to not be able to comment out required_conan_version"""
        client = TestClient()
        conanfile = textwrap.dedent("""
                            from conan import missing_import
                            # required_conan_version = ">=100.0"
                            class Lib(ConanFile):
                                pass
                            """)
        client.save({"conanfile.py": conanfile})
        client.run("export . --name=pkg --version=1.0", assert_error=False)
        self.assertNotIn("Current Conan version (%s) does not satisfy the defined one (>=100.0)"
                         % __version__, client.out)
