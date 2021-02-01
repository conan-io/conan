import textwrap
import unittest

from conans.test.utils.tools import TestClient


class InitTest(unittest.TestCase):
    def test_wrong_init(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Lib(ConanFile):
                def init(self):
                    random_error
            """)

        client.save({"conanfile.py": conanfile})
        client.run("inspect .", assert_error=True)
        self.assertIn("Error in init() method, line 5", client.out)
        self.assertIn("name 'random_error' is not defined", client.out)

    def test_init(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile, load
            import os
            import json
            class Lib(ConanFile):
                exports = "data.json"
                def init(self):
                    data = load(os.path.join(self.recipe_folder, "data.json"))
                    d = json.loads(data)
                    self.license = d["license"]
                    self.description = d["description"]
                def build(self):
                    self.output.info("LICENSE: %s" % self.license)
            """)
        data = '{"license": "MIT", "description": "MyDescription"}'
        client.save({"conanfile.py": conanfile,
                     "data.json": data})

        client.run("inspect .")
        self.assertIn("description: MyDescription", client.out)
        self.assertIn("license: MIT", client.out)
        client.run("create . pkg/0.1@user/testing")
        client.run("inspect pkg/0.1@user/testing")
        self.assertIn("description: MyDescription", client.out)
        self.assertIn("license: MIT", client.out)
