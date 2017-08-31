import platform
import unittest

from conans.test.utils.tools import TestClient


class SymlinkPackageTest(unittest.TestCase):

    def test_symlink_created(self):
        if platform.system() != "Linux" and platform.system() != "Darwin":
            return

        conanfile = """from conans import ConanFile
import os


class TestlinksConan(ConanFile):
    name = "test_links"
    version = "1.0"
    settings = "os", "compiler", "build_type", "arch"
    generators = "cmake"

    def build(self):
        os.makedirs("foo/test/bar")
        with open("foo/test/bar/hello_world.txt", "w"):
            os.utime("foo/test/bar/hello_world.txt", None)
        os.symlink("test/bar", "foo/test_link")

    def package(self):
        self.copy("*", src=".", dst=".", links=True)
"""
        test_package = """from conans import ConanFile, CMake
from conans.errors import ConanException
import os


channel = os.getenv("CONAN_CHANNEL", "stable")
username = os.getenv("CONAN_USERNAME", "plex")


class TestlinksTestConan(ConanFile):
    settings = "os", "compiler", "build_type", "arch"
    requires = "test_links/1.0@%s/%s" % (username, channel)
    generators = "cmake"

    def test(self):
        foopath = self.deps_cpp_info["test_links"].rootpath + "/foo/test_link"
        assert os.path.exists(os.path.join(foopath, "hello_world.txt"))
        if not os.path.islink(foopath):
            raise ConanException("Not a link!")
"""
        client = TestClient()
        client.save({"conanfile.py": conanfile,
                     "test_package/conanfile.py": test_package})

        client.run("test_package")


if __name__ == '__main__':
    unittest.main()
