import unittest

from conans.test.utils.tools import TestClient


class LoadRequirementsTextFileTest(unittest.TestCase):

    def test_load_reqs_from_text_file(self):
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
        client.run("create . hello0/0.1@user/channel")

        for i in (0, 1, 2):
            reqs = "hello%s/0.1@user/channel" % i
            client.save({"conanfile.py": conanfile,
                         "reqs.txt": reqs})
            client.run("create . hello%s/0.1@user/channel" % (i + 1))

        client.run("install --reference=hello3/0.1@user/channel")
        self.assertIn("hello0/0.1@user/channel from local", client.out)
        self.assertIn("hello1/0.1@user/channel from local", client.out)
        self.assertIn("hello2/0.1@user/channel from local", client.out)
        self.assertIn("hello3/0.1@user/channel from local", client.out)
