import unittest

from conans.test.utils.tools import TestClient


class CppInfoScopeTest(unittest.TestCase):

    def test_cpp_info_scope(self):
        client = TestClient()
        conanfile = """from conans import ConanFile
class TestConan(ConanFile):
    def package(self):
        self.cpp_info.includedirs = ["inc"]
    """
        client.save({"conanfile.py": conanfile})
        client.run("create . Pkg/0.1@lasote/channel", assert_error=True)
        self.assertIn("ERROR: Pkg/0.1@lasote/channel: Error in package() method, line 4",
                      client.out)
        self.assertIn("AttributeError: 'NoneType' object has no attribute 'includedirs'",
                      client.out)
