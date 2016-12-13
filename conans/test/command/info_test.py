import unittest
from conans.test.tools import TestClient
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.paths import CONANFILE
import textwrap


class InfoTest(unittest.TestCase):

    def _create(self, number, version, deps=None, deps_dev=None, export=True):
        files = cpp_hello_conan_files(number, version, deps, build=False)
        files[CONANFILE] = files[CONANFILE].replace("config(", "configure(")
        if deps_dev:
            files[CONANFILE] = files[CONANFILE].replace("exports = '*'", """exports = '*'
    dev_requires=%s
""" % ",".join('"%s"' % d for d in deps_dev))

        self.client.save(files, clean_first=True)
        if export:
            self.client.run("export lasote/stable")
            expected_output = textwrap.dedent(
                """\
                WARN: Conanfile doesn't have 'url'.
                It is recommended to add it as attribute
                WARN: Conanfile doesn't have 'license'.
                It is recommended to add it as attribute
                WARN: Conanfile doesn't have 'description'.
                It is recommended to add it as attribute""")
            self.assertIn(expected_output, self.client.user_io.out)

        if number != "Hello2":
            files[CONANFILE] = files[CONANFILE].replace('version = "0.1"',
                                                        'version = "0.1"\n'
                                                        '    url= "myurl"\n'
                                                        '    license = "MIT"')
        else:
            files[CONANFILE] = files[CONANFILE].replace('version = "0.1"',
                                                        'version = "0.1"\n'
                                                        '    url= "myurl"\n'
                                                        '    license = "MIT", "GPL"')

        self.client.save(files)
        if export:
            self.client.run("export lasote/stable")
            self.assertNotIn("WARN: Conanfile doesn't have 'url'", self.client.user_io.out)

    def reuse_test(self):
        self.client = TestClient()
        self._create("Hello0", "0.1")
        self._create("Hello1", "0.1", ["Hello0/0.1@lasote/stable"])
        self._create("Hello2", "0.1", ["Hello1/0.1@lasote/stable"], export=False)

        self.client.run("info -u")
        expected_output = textwrap.dedent(
            """\
            Hello2/0.1@PROJECT
                URL: myurl
                Licenses: MIT, GPL
                Requires:
                    Hello1/0.1@lasote/stable
            Hello0/0.1@lasote/stable
                Remote: None
                URL: myurl
                License: MIT
                Updates: You have the latest version (None)
                Required by:
                    Hello1/0.1@lasote/stable
            Hello1/0.1@lasote/stable
                Remote: None
                URL: myurl
                License: MIT
                Updates: You have the latest version (None)
                Required by:
                    Hello2/0.1@PROJECT
                Requires:
                    Hello0/0.1@lasote/stable""")
        self.assertIn(expected_output, self.client.user_io.out)

        self.client.run("info -u --only=url")
        expected_output = textwrap.dedent(
            """\
            Hello2/0.1@PROJECT
                URL: myurl
            Hello0/0.1@lasote/stable
                URL: myurl
            Hello1/0.1@lasote/stable
                URL: myurl""")
        self.assertIn(expected_output, self.client.user_io.out)
        self.client.run("info -u --only=url,license")
        expected_output = textwrap.dedent(
            """\
            Hello2/0.1@PROJECT
                URL: myurl
                Licenses: MIT, GPL
            Hello0/0.1@lasote/stable
                URL: myurl
                License: MIT
            Hello1/0.1@lasote/stable
                URL: myurl
                License: MIT""")
        self.assertIn(expected_output, self.client.user_io.out)

    def build_order_test(self):
        self.client = TestClient()
        self._create("Hello0", "0.1")
        self._create("Hello1", "0.1", ["Hello0/0.1@lasote/stable"])
        self._create("Hello2", "0.1", ["Hello1/0.1@lasote/stable"], export=False)

        self.client.run("info -bo=Hello0/0.1@lasote/stable")
        self.assertIn("[Hello0/0.1@lasote/stable], [Hello1/0.1@lasote/stable]",
                      self.client.user_io.out)

        self.client.run("info -bo=Hello1/0.1@lasote/stable")
        self.assertIn("[Hello1/0.1@lasote/stable]", self.client.user_io.out)

        self.client.run("info -bo=Hello1/0.1@lasote/stable -bo=Hello0/0.1@lasote/stable")
        self.assertIn("[Hello0/0.1@lasote/stable], [Hello1/0.1@lasote/stable]",
                      self.client.user_io.out)

        self.client.run("info Hello1/0.1@lasote/stable -bo=Hello0/0.1@lasote/stable")
        self.assertEqual("[Hello0/0.1@lasote/stable], [Hello1/0.1@lasote/stable]\n",
                         self.client.user_io.out)

    def diamond_build_order_test(self):
        self.client = TestClient()
        self._create("LibA", "0.1")
        self._create("Dev1", "0.1")
        self._create("LibE", "0.1", deps_dev=["Dev1/0.1@lasote/stable"])
        self._create("LibF", "0.1")
        self._create("LibG", "0.1")
        self._create("Dev2", "0.1", deps=["LibG/0.1@lasote/stable"])

        self._create("LibB", "0.1", ["LibA/0.1@lasote/stable", "LibE/0.1@lasote/stable"])
        self._create("LibC", "0.1", ["LibA/0.1@lasote/stable", "LibF/0.1@lasote/stable"],
                     deps_dev=["Dev2/0.1@lasote/stable"])

        self._create("LibD", "0.1", ["LibB/0.1@lasote/stable", "LibC/0.1@lasote/stable"],
                     export=False)

        self.client.run("info -bo=LibA/0.1@lasote/stable")
        self.assertIn("[LibA/0.1@lasote/stable], "
                      "[LibB/0.1@lasote/stable, LibC/0.1@lasote/stable]",
                      self.client.user_io.out)
        self.client.run("info -bo=LibB/0.1@lasote/stable")
        self.assertIn("[LibB/0.1@lasote/stable]", self.client.user_io.out)
        self.client.run("info -bo=LibE/0.1@lasote/stable")
        self.assertIn("[LibE/0.1@lasote/stable], [LibB/0.1@lasote/stable]",
                      self.client.user_io.out)
        self.client.run("info -bo=LibF/0.1@lasote/stable")
        self.assertIn("[LibF/0.1@lasote/stable], [LibC/0.1@lasote/stable]",
                      self.client.user_io.out)
        self.client.run("info -bo=Dev1/0.1@lasote/stable")
        self.assertEqual("\n", self.client.user_io.out)
        self.client.run("info --scope=LibE:dev=True -bo=Dev1/0.1@lasote/stable")
        self.assertIn("[Dev1/0.1@lasote/stable], [LibE/0.1@lasote/stable], "
                      "[LibB/0.1@lasote/stable]", self.client.user_io.out)
        self.client.run("info -bo=LibG/0.1@lasote/stable")
        self.assertEqual("\n", self.client.user_io.out)
        self.client.run("info --scope=LibC:dev=True -bo=LibG/0.1@lasote/stable")
        self.assertIn("[LibG/0.1@lasote/stable], [Dev2/0.1@lasote/stable], "
                      "[LibC/0.1@lasote/stable]", self.client.user_io.out)

        self.client.run("info --build_order=ALL")
        self.assertIn("[LibA/0.1@lasote/stable, LibE/0.1@lasote/stable, LibF/0.1@lasote/stable], "
                      "[LibB/0.1@lasote/stable, LibC/0.1@lasote/stable]",
                      self.client.user_io.out)

        self.client.run("info --build_order=ALL --scope=ALL:dev=True")
        self.assertIn("[Dev1/0.1@lasote/stable, LibG/0.1@lasote/stable], "
                      "[Dev2/0.1@lasote/stable, LibA/0.1@lasote/stable, LibE/0.1@lasote/stable, "
                      "LibF/0.1@lasote/stable], [LibB/0.1@lasote/stable, LibC/0.1@lasote/stable]",
                      self.client.user_io.out)
