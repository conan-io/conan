import unittest
from conans.test.tools import TestClient
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.paths import CONANFILE
import textwrap


class InfoTest(unittest.TestCase):

    def _create(self, number, version, deps=None, export=True):
        files = cpp_hello_conan_files(number, version, deps)
        # To avoid building
        files = {CONANFILE: files[CONANFILE].replace("build(", "build2(")}

        self.client.save(files, clean_first=True)
        if export:
            self.client.run("export lasote/stable")
            expected_output = textwrap.dedent(
                """\
                WARN: Conanfile doesn't have 'url'.
                It is recommended to add your repo URL as attribute
                WARN: Conanfile doesn't have a 'license'.
                It is recommended to add the package license as attribute""")
            self.assertIn(expected_output, self.client.user_io.out)

        files[CONANFILE] = files[CONANFILE].replace('version = "0.1"',
                                                    'version = "0.1"\n'
                                                    '    url= "myurl"\n'
                                                    '    license = "MIT"')
        self.client.save(files)
        if export:
            self.client.run("export lasote/stable")
            self.assertNotIn("WARN: Conanfile doesn't have 'url'", self.client.user_io.out)

    def reuse_test(self):
        self.client = TestClient()
        self._create("Hello0", "0.1")
        self._create("Hello1", "0.1", ["Hello0/0.1@lasote/stable"])
        self._create("Hello2", "0.1", ["Hello1/0.1@lasote/stable"], export=False)

        self.client.run("info")
        expected_output = textwrap.dedent(
            """\
            Hello2/0.1@PROJECT
                URL: myurl
                License: MIT
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
