import unittest

from conans.test.utils.tools import TestClient


class LoadRequirementsTextFileTest(unittest.TestCase):

    def load_reqs_from_text_file_test(self):
        client = TestClient()
        conanfile = """from conans import ConanFile, load
def reqs():
    try:
        content = load("reqs.txt")
        lines = [line for line in content.splitlines() if line]
        return tuple(lines)
    except:
        return None

class Test(ConanFile):
    exports = "reqs.txt"
    requires = reqs()
"""
        client.save({"conanfile.py": conanfile})
        client.run("create . Hello0/0.1@user/channel")

        for i in (0, 1, 2):
            reqs = "Hello%s/0.1@user/channel" % i
            client.save({"conanfile.py": conanfile,
                         "reqs.txt": reqs})
            client.run("create . Hello%s/0.1@user/channel" % (i + 1))

        client.run("install Hello3/0.1@user/channel")
        self.assertIn("Hello0/0.1@user/channel from local", client.out)
        self.assertIn("Hello1/0.1@user/channel from local", client.out)
        self.assertIn("Hello2/0.1@user/channel from local", client.out)
        self.assertIn("Hello3/0.1@user/channel from local", client.out)
