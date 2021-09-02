import textwrap
import unittest


from conans.paths import CONANFILE
from conans.test.utils.tools import TestClient

conanfile = textwrap.dedent('''
    from conans import ConanFile

    class ConanLib(ConanFile):
        name = "Hello0"
        version = "0.1"

        def source(self):
            self.output.info("Running source!")
''')


class MismatchReference(unittest.TestCase):
    def test_imports(self):
        client = TestClient()
        client.save({CONANFILE: conanfile})
        client.run("export . lasote/stable")
        client.run("install Hello0/0.1@lasote/stable --build=missing")
        client.run("imports hello0/0.1@lasote/stable", assert_error=True)
        # Reference interpreted as a path, so no valid path
        self.assertIn("Parameter 'path' cannot be a reference", client.out)

    def test_package(self):
        client = TestClient()
        client.save({CONANFILE: conanfile})
        client.run("export . lasote/stable")
        client.run("install Hello0/0.1@lasote/stable --build=missing")
        client.run("export-pkg . hello0/0.1@lasote/stable", assert_error=True)
        self.assertIn("ERROR: Package recipe with name hello0!=Hello0", client.out)
