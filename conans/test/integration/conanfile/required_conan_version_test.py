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

    def test_comment_after_required_conan_version(self):
        """
        An error used to pop out if you tried to add a comment in the same line than
        required_conan_version, as it was trying to compare against >=10.0 # This should work
        instead of just >= 10.0
        """
        client = TestClient()
        conanfile = textwrap.dedent("""
                    from conan import ConanFile
                    from LIB_THAT_DOES_NOT_EXIST import MADE_UP_NAME
                    required_conan_version = ">=10.0" # This should work
                    class Lib(ConanFile):
                        pass
                    """)
        client.save({"conanfile.py": conanfile})
        client.run("export . --name=pkg --version=1.0", assert_error=True)
        self.assertIn("Current Conan version (%s) does not satisfy the defined one (>=10.0)"
                      % __version__, client.out)

    def test_commented_out_required_conan_version(self):
        """
        Used to not be able to comment out required_conan_version if we had to fall back
        to regex check because of an error importing the recipe
        """
        client = TestClient()
        conanfile = textwrap.dedent("""
                    from conan import ConanFile
                    from LIB_THAT_DOES_NOT_EXIST import MADE_UP_NAME
                    required_conan_version = ">=1.0" # required_conan_version = ">=100.0"
                    class Lib(ConanFile):
                        pass
                    """)
        client.save({"conanfile.py": conanfile})
        client.run("export . --name=pkg --version=10.0", assert_error=True)
        self.assertNotIn("Current Conan version (%s) does not satisfy the defined one (>=1.0)"
                      % __version__, client.out)

        client = TestClient()
        conanfile = textwrap.dedent("""
                    from conan import ConanFile
                    from LIB_THAT_DOES_NOT_EXIST import MADE_UP_NAME
                    # required_conan_version = ">=10.0"
                    class Lib(ConanFile):
                        pass
                    """)
        client.save({"conanfile.py": conanfile})
        client.run("export . --name=pkg --version=1.0", assert_error=True)
        self.assertNotIn("Current Conan version (%s) does not satisfy the defined one (>=10.0)"
                         % __version__, client.out)

    def test_required_conan_version_invalid_syntax(self):
        """ required_conan_version used to warn of mismatching versions if spaces were present,
         but now we have a nicer error"""
        # https://github.com/conan-io/conan/issues/12692
        client = TestClient()
        conanfile = textwrap.dedent("""
                    from conan import ConanFile
                    required_conan_version = ">= 1.0"
                    class Lib(ConanFile):
                        pass""")
        client.save({"conanfile.py": conanfile})
        client.run("export . --name=pkg --version=1.0", assert_error=True)
        self.assertNotIn(f"Current Conan version ({__version__}) does not satisfy the defined one "
                        "(>= 1.0)", client.out)
        self.assertIn("Error parsing version range >=", client.out)
