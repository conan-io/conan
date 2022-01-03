import unittest
from conans.client.command import ERROR_INVALID_SYSTEM_REQUIREMENTS
from conans.test.utils.tools import TestClient


class InvalidSystemRequirementsTest(unittest.TestCase):
    def test_create_method(self):
        self.client = TestClient()
        self.client.save({"conanfile.py": """
from conans import ConanFile
from conans.errors import ConanInvalidSystemRequirements

class MyPkg(ConanFile):
    settings = "os", "compiler", "build_type", "arch"

    def build_requirements(self):
        raise ConanInvalidSystemRequirements("Some package missed")

"""})

        error = self.client.run("create . name/ver@jgsogo/test", assert_error=True)
        self.assertEqual(error, ERROR_INVALID_SYSTEM_REQUIREMENTS)
        self.assertIn("Invalid system requirements: Some package missed", self.client.out)

