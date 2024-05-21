import unittest

from conan.cli.exit_codes import ERROR_INVALID_CONFIGURATION
from conan.test.utils.tools import TestClient


class InvalidConfigurationTest(unittest.TestCase):

    def setUp(self):
        self.client = TestClient()
        self.client.save({"conanfile.py": """
from conan import ConanFile
from conan.errors import ConanInvalidConfiguration

class MyPkg(ConanFile):
    settings = "os", "compiler", "build_type", "arch"

    def configure(self):
        if self.settings.compiler.version == "190":
            raise ConanInvalidConfiguration("user says that compiler.version=12 is invalid")

    """})
        settings = "-s os=Windows -s compiler=msvc -s compiler.version={ver} "\
                   "-s compiler.runtime=dynamic"
        self.settings_msvc15 = settings.format(ver="192")
        self.settings_msvc12 = settings.format(ver="190")

    def test_install_method(self):
        self.client.run("install . %s" % self.settings_msvc15)

        error = self.client.run("install . %s" % self.settings_msvc12, assert_error=True)
        self.assertEqual(error, ERROR_INVALID_CONFIGURATION)
        self.assertIn("Invalid configuration: user says that compiler.version=12 is invalid",
                      self.client.out)

    def test_info_method(self):
        self.client.run("graph info . %s" % self.settings_msvc15)

        error = self.client.run("graph info . %s" % self.settings_msvc12,
                                assert_error=True)
        self.assertEqual(error, ERROR_INVALID_CONFIGURATION)
        self.assertIn("ERROR: conanfile.py: Invalid configuration: "
                      "user says that compiler.version=12 is invalid", self.client.out)

    def test_create_method(self):
        self.client.run("create . --name=name --version=ver --user=jgsogo --channel=test %s" % self.settings_msvc15)

        error = self.client.run("create . --name=name --version=ver --user=jgsogo --channel=test %s" % self.settings_msvc12,
                                assert_error=True)
        self.assertEqual(error, ERROR_INVALID_CONFIGURATION)
        self.assertIn("name/ver@jgsogo/test: Invalid configuration: user says that "
                      "compiler.version=12 is invalid", self.client.out)

    def test_as_requirement(self):
        self.client.run("create . --name=name --version=ver %s" % self.settings_msvc15)
        self.client.save({"other/conanfile.py": """
from conan import ConanFile
from conan.errors import ConanInvalidConfiguration

class MyPkg(ConanFile):
    requires = "name/ver"
    settings = "os", "compiler", "build_type", "arch"
    """})
        self.client.run("create other/ --name=other --version=1.0 %s" % self.settings_msvc15)

        error = self.client.run("create other/ --name=other --version=1.0 %s" % self.settings_msvc12,
                                assert_error=True)
        self.assertEqual(error, ERROR_INVALID_CONFIGURATION)
        self.assertIn("name/ver: Invalid configuration: user says that "
                      "compiler.version=12 is invalid", self.client.out)
