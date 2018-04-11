import unittest
from conans.test.utils.tools import TestClient, TestServer
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.paths import CONANFILE
import os
from conans.util.files import load, save


class InfoTest(unittest.TestCase):

    def setUp(self):
        test_server = TestServer(users={"lu": "mypass"})
        self.servers = {"default": test_server}
        self.clients = {}

    def _export(self, name=0, version=None, deps=None):
        client = TestClient(servers=self.servers, users={"default": [("lu", "mypass")]})
        self.clients[name] = client
        # Not necessary to actually build binaries
        files = cpp_hello_conan_files(name, version, deps, build=False)
        client.save(files, clean_first=True)
        client.run("export . lu/st")
        client.run("upload %s/%s@lu/st" % (name, version))

    def assert_last_line(self, client, line):
        lastline = str(client.user_io.out).splitlines()[-1]
        self.assertEquals(lastline, line)

    def info_build_test(self):
        """Test that the output of 'conan info --build' is correct

                    +-----------+
           +------> |  H0       | <--------+
           |        +------+----+          |
   private |               ^               |private
           |               |               |
      +----+-----+    +----+------+   +----+------+
      |  H1a     |    | H1b       |   | H1c       |
      +----+-----+    +-----------+   +----+------+
           ^                               ^
           |                               |
           |                               |
+----------+-+                     +-------+------+
|  H2a       | <------+    +-----> |   H2c        |
+------------+        |    |       +--------------+
                      |    |
                  +---+----+---+
                  |  H3        |
                  +------------+

        """

        self._export("H0", "0.1")

        self._export("H1a", "0.1", deps=[("H0/0.1@lu/st", "private")])
        self._export("H1b", "0.1", deps=["H0/0.1@lu/st"])
        self._export("H1c", "0.1", deps=[("H0/0.1@lu/st", "private")])

        self._export("H2a", "0.1", deps=["H1a/0.1@lu/st"])
        self._export("H2c", "0.1", deps=["H1c/0.1@lu/st"])

        self._export("H3", "0.1", deps=["H2a/0.1@lu/st",
                                        "H2c/0.1@lu/st"])

        # If we install H3 we need to build all except H1b
        self.clients["H3"].run("info . --build missing")
        self.assert_last_line(self.clients["H3"],
                              "H0/0.1@lu/st, H1a/0.1@lu/st, H1c/0.1@lu/st, H2a/0.1@lu/st, H2c/0.1@lu/st")

        # If we install H0 we need to build nothing (current project)
        self.clients["H0"].run("info ./conanfile.py --build missing")
        self.assert_last_line(self.clients["H0"], "")

        # If we install H0 we need to build H0
        self.clients["H1a"].run("info conanfile.py --build missing")
        self.assert_last_line(self.clients["H1a"], "H0/0.1@lu/st")

        # If we build and upload H1a and H1c, no more H0 (private) is required
        self.clients["H3"].run("install H1a/0.1@lu/st --build ")
        self.clients["H3"].run("install H1c/0.1@lu/st --build ")
        self.clients["H3"].run("upload H1a/0.1@lu/st --all")
        self.clients["H3"].run("upload H1c/0.1@lu/st --all")

        self.clients["H3"].run("remove '*' -f")
        self.clients["H3"].run("info . --build missing")
        self.assert_last_line(self.clients["H3"],
                              "H2a/0.1@lu/st, H2c/0.1@lu/st")

        # But if we force to build all, all nodes have to be built
        self.clients["H3"].run("remove '*' -f")
        self.clients["H3"].run("info ./conanfile.py --build")
        self.assert_last_line(self.clients["H3"],
                              "H0/0.1@lu/st, H1a/0.1@lu/st, H1c/0.1@lu/st, H2a/0.1@lu/st, H2c/0.1@lu/st")

        # Now upgrade the recipe H1a and upload it (but not the package)
        # so the package become outdated
        conanfile_path = os.path.join(self.clients["H1a"].current_folder, CONANFILE)
        conanfile = load(conanfile_path)
        conanfile += "\n# MODIFIED"
        save(conanfile_path, conanfile)
        self.clients["H1a"].run("export . lu/st")
        self.clients["H1a"].run("upload H1a/0.1@lu/st")  # NOW IS OUTDATED!

        # Without build outdated the built packages are the same
        self.clients["H3"].run("remove '*' -f")
        self.clients["H3"].run("info conanfile.py --build missing")
        self.assert_last_line(self.clients["H3"],
                              "H2a/0.1@lu/st, H2c/0.1@lu/st")

        # But with build outdated we have to build the private H0 (but only once) and H1a
        self.clients["H3"].run("remove '*' -f")
        self.clients["H3"].run("info . --build outdated")
        self.assert_last_line(self.clients["H3"],
                              "H0/0.1@lu/st, H1a/0.1@lu/st, H2a/0.1@lu/st, H2c/0.1@lu/st")
