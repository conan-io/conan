import unittest

from conans.test.utils.tools import TestClient


class ExportTest(unittest.TestCase):

    def export_without_full_reference_test(self):
        client = TestClient()
        client.save({"conanfile.py": """from conans import ConanFile
class MyPkg(ConanFile):
    pass
"""})
        error = client.run("export lasote/channel", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("conanfile didn't specify name", client.out)

        client.save({"conanfile.py": """from conans import ConanFile
class MyPkg(ConanFile):
    name="Lib"
"""})
        error = client.run("export lasote/channel", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("conanfile didn't specify version", client.out)

        client.save({"conanfile.py": """from conans import ConanFile
class MyPkg(ConanFile):
    pass
"""})
        client.run("export lib/1.0@lasote/channel")
        self.assertIn("lib/1.0@lasote/channel: A new conanfile.py version was exported",
                      client.out)

        client.save({"conanfile.py": """from conans import ConanFile
class MyPkg(ConanFile):
    name="Lib"
    version="1.0"
"""})
        client.run("export lasote")
        self.assertIn("Lib/1.0@lasote/testing: A new conanfile.py version was exported",
                      client.out)
