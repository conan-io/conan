import unittest

from conans.test.utils.tools import TestClient

base_conanfile = """from conans import ConanFile
        
class MyConanfile(ConanFile):

    generators = %s
"""


class GeneratorsArguments(unittest.TestCase):

    def test_invalid_args(self):
        gen_dict = {"cmake": {"arg1": 23, "arg2": "44"}}
        conanfile = base_conanfile % str(gen_dict)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("create . lib/1.0@conan/stable")


