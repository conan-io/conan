import os
import unittest


from conans.paths import CONANFILE
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient, TestServer
from conans.util.files import load, save


class InfoTest(unittest.TestCase):

    def setUp(self):
        test_server = TestServer(users={"lu": "mypass"})
        self.servers = {"default": test_server}
        self.clients = {}

        # Build a complex graph
        """
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

        self._export("H3", "0.1", deps=["H2a/0.1@lu/st", "H2c/0.1@lu/st"])

    def _export(self, name=0, version=None, deps=None):
        client = TestClient(servers=self.servers, users={"default": [("lu", "mypass")]})
        self.clients[name] = client
        # Not necessary to actually build binaries
        conanfile = GenConanfile(name, version)
        for dep in deps or []:
            try:
                ref, private = dep
            except ValueError:
                ref, private = dep, None
            conanfile.with_require(ref, private=private)

        client.save({"conanfile.py": conanfile}, clean_first=True)
        client.run("export . lu/st")
        client.run("upload %s/%s@lu/st" % (name, version))

    def assert_last_line(self, client, line):
        lastline = str(client.out).splitlines()[-1]
        self.assertEqual(lastline, line)

    def test_info_build(self):
        """ Test that the output of 'conan info --build' is correct """
        # If we install H3 we need to build all except H1b
        self.clients["H3"].run("info . --build missing")
        self.assert_last_line(self.clients["H3"],
                              "H0/0.1@lu/st, H1a/0.1@lu/st, H1c/0.1@lu/st, "
                              "H2a/0.1@lu/st, H2c/0.1@lu/st")

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
                              "H0/0.1@lu/st, H1a/0.1@lu/st, H1c/0.1@lu/st, "
                              "H2a/0.1@lu/st, H2c/0.1@lu/st")

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

        if not self.clients["H3"].cache.config.revisions_enabled:
            self.assert_last_line(self.clients["H3"], "H2a/0.1@lu/st, H2c/0.1@lu/st")
        else:  # When revisions are enabled we just created a new one for H1a
            # when modifing the recipe so we need to rebuild it and its private H0
            self.assert_last_line(self.clients["H3"], 'H0/0.1@lu/st, H1a/0.1@lu/st, '
                                                      'H2a/0.1@lu/st, H2c/0.1@lu/st')

        # But with build outdated we have to build the private H0 (but only once) and H1a
        self.clients["H3"].run("remove '*' -f")
        self.clients["H3"].run("info . --build outdated")
        self.assert_last_line(self.clients["H3"],
                              "H0/0.1@lu/st, H1a/0.1@lu/st, H2a/0.1@lu/st, H2c/0.1@lu/st")

    def test_json_output_build(self):
        """ Test that the output of 'conan info --build' to json file is correct """
        json_file = os.path.join(temp_folder(), "output.json")
        json_output = '["H0/0.1@lu/st", "H1a/0.1@lu/st", "H1c/0.1@lu/st", ' \
                      '"H2a/0.1@lu/st", "H2c/0.1@lu/st"]'

        self.clients["H3"].run("info . --build missing --json=\"{}\"".format(json_file))
        self.assertEqual(load(json_file), json_output)

        self.clients["H3"].run("info . --build missing --json")
        self.assert_last_line(self.clients["H3"], json_output)
