import unittest

from conans.test.utils.tools import TestClient

base_conanfile = """from conans import ConanFile
        
class MyConanfile(ConanFile):

    generators = %s
"""

custom_gen = """
from conans.model import Generator
        
class MyGenerator(Generator):
    @property
    def filename(self):
        return "mygenerator.file"

    @property
    def content(self):
        return "whatever contents the generator produces"
    
%s
"""


class GeneratorsArguments(unittest.TestCase):

    def test_args_not_allowed(self):
        gen_dict = {"cmake": {"arg1": 23, "arg2": "44"}}
        conanfile = base_conanfile % str(gen_dict)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        error = client.run("create . lib/1.0@conan/stable", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: This generator do not accept arguments", client.out)

        # Now with a custom generator
        gen_dict = {"MyGenerator": {"arg1": 23, "arg2": "44"}}
        conanfile = custom_gen % "" + base_conanfile % str(gen_dict)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        error = client.run("create . lib/1.0@conan/stable", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: This generator do not accept arguments", client.out)

    def test_declare_custom_args(self):
        gen_dict = {"MyGenerator": {"arg1": 23, "arg2": "44"}}
        args_method = """
    def init_args(self, arg1, arg2):
        self.conanfile.output.warn("ARG1=%s" % arg1)
        self.conanfile.output.warn("ARG2=%s" % arg2)          
          
"""
        conanfile = custom_gen % args_method + base_conanfile % str(gen_dict)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("create . lib/1.0@conan/stable")
        self.assertIn("ARG1=23", client.out)
        self.assertIn("ARG2=44", client.out)

        # Now pass wrong args
        gen_dict = {"MyGenerator": {"badarg": 23, "arg2": "44"}}
        conanfile = custom_gen % args_method + base_conanfile % str(gen_dict)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        error = client.run("create . lib/1.0@conan/stable", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("Invalid arguments passed to 'MyGenerator' generator: "
                      "init_args() got an unexpected keyword argument 'badarg'", client.out)