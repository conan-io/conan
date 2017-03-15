import unittest
from conans.test.utils.tools import TestClient
import random
import string


class ConanfileHelpersTest(unittest.TestCase):

    def test_replace_in_file(self):
        for libname in [''.join(random.choice(string.ascii_lowercase) for _ in range(5))
                        for _ in range(5)]:
            helpers = '''
def build_helper(output):
    output.info("Building %d!")
    '''
            other_helper = '''
def source_helper(output):
    output.info("Source %d!")
    '''
            file_content = '''
from conans import ConanFile
from {libname} import build_helper
from {libname}s.other import source_helper

class ConanFileToolsTest(ConanFile):
    name = "test"
    version = "1.9"
    exports = "*"

    def source(self):
        source_helper(self.output)

    def build(self):
        build_helper(self.output)
    '''
            file_content2 = '''
from a{libname} import build_helper
from a{libname}s.other import source_helper
from conans import ConanFile


class ConanFileToolsTest(ConanFile):
    name = "test2"
    version = "2.3"
    exports = "*"

    def source(self):
        source_helper(self.output)

    def build(self):
        build_helper(self.output)
    '''
            files = {"%s.py" % libname: helpers % 1,
                     "%ss/__init__.py" % libname: "",
                     "%ss/other.py" % libname: other_helper % 1,
                     "conanfile.py": file_content.format(libname=libname)}

            client = TestClient()
            client.save(files)
            client.run("export lasote/testing")

            client2 = TestClient(client.base_folder)
            files = {"a%s.py" % libname: helpers % 2,
                     "a%ss/__init__.py" % libname: "",
                     "a%ss/other.py" % libname: other_helper % 2,
                     "conanfile.py": file_content2.format(libname=libname)}
            client2.save(files)
            client2.run("export lasote/testing")

            client3 = TestClient(client.base_folder)
            files = {"conanfile.txt": """[requires]
                                        test/1.9@lasote/testing\n
                                        test2/2.3@lasote/testing"""}
            client3.save(files)
            client3.run("install --build")
            # print client3.user_io.out
            self.assertIn("Building 1!", client3.user_io.out)
            self.assertIn("Source 1!", client3.user_io.out)
            self.assertIn("Building 2!", client3.user_io.out)
            self.assertIn("Source 2!", client3.user_io.out)
