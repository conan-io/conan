import textwrap
import unittest

from conan.test.utils.tools import TestClient


class InitTest(unittest.TestCase):
    def test_wrong_init(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Lib(ConanFile):
                def init(self):
                    random_error
            """)

        client.save({"conanfile.py": conanfile})
        client.run("export .", assert_error=True)
        self.assertIn("Error in init() method, line 5", client.out)
        self.assertIn("name 'random_error' is not defined", client.out)

    def test_init(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.files import load
            import os
            import json
            class Lib(ConanFile):
                exports = "data.json"
                def init(self):
                    data = load(self, os.path.join(self.recipe_folder, "data.json"))
                    d = json.loads(data)
                    self.license = d["license"]
                    self.description = d["description"]
                def export(self):
                    self.output.info("description: %s" % self.description)
                    self.output.info("license: %s" % self.license)
                def build(self):
                    self.output.info("description: %s" % self.description)
                    self.output.info("license: %s" % self.license)
            """)
        data = '{"license": "MIT", "description": "MyDescription"}'
        client.save({"conanfile.py": conanfile,
                     "data.json": data})

        client.run("export . --name=pkg --version=version")
        self.assertIn("description: MyDescription", client.out)
        self.assertIn("license: MIT", client.out)
        client.run("create . --name=pkg --version=0.1 --user=user --channel=testing")
        self.assertIn("description: MyDescription", client.out)
        self.assertIn("license: MIT", client.out)
