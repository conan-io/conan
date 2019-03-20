import textwrap
import unittest

from conans.client.tools import environment_append
from conans.paths import CONANFILE
from conans.test.utils.tools import TestClient


class ConflictDiamondTest(unittest.TestCase):
    conanfile = textwrap.dedent("""
        from conans import ConanFile

        class HelloReuseConan(ConanFile):
            name = "%s"
            version = "%s"
            requires = %s
        """)

    def _export(self, name, version, deps=None, export=True):
        deps = ", ".join(['"%s"' % d for d in deps or []]) or '""'
        conanfile = self.conanfile % (name, version, deps)
        files = {CONANFILE: conanfile}
        self.client.save(files, clean_first=True)
        if export:
            self.client.run("export . lasote/stable")

    def setUp(self):
        self.client = TestClient()
        self._export("Hello0", "0.1")
        self._export("Hello0", "0.2")
        self._export("Hello1", "0.1", ["Hello0/0.1@lasote/stable"])
        self._export("Hello2", "0.1", ["Hello0/0.2@lasote/stable"])

    def test_conflict(self):
        """ There is a conflict in the graph: branches with requirement in different
            version, Conan will raise
        """
        self._export("Hello3", "0.1", ["Hello1/0.1@lasote/stable", "Hello2/0.1@lasote/stable"],
                     export=False)
        self.client.run("install . --build missing", assert_error=True)
        self.assertIn("Conflict in Hello2/0.1@lasote/stable", self.client.user_io.out)
        self.assertNotIn("Generated conaninfo.txt", self.client.user_io.out)

    def test_override_silent(self):
        """ There is a conflict in the graph, but the consumer project depends on the conflicting
            library, so all the graph will use the version from the consumer project
        """
        self._export("Hello3", "0.1",
                     ["Hello1/0.1@lasote/stable", "Hello2/0.1@lasote/stable",
                      "Hello0/0.1@lasote/stable"], export=False)
        self.client.run("install . --build missing", assert_error=False)
        self.assertIn("Hello2/0.1@lasote/stable requirement Hello0/0.2@lasote/stable overridden"
                      " by Hello3/0.1@None/None to Hello0/0.1@lasote/stable",
                      self.client.user_io.out)

    def test_error_on_override(self):
        """ Given a conflict in dependencies that is overridden by the consumer project, instead
            of silently output a message, the user can force an error using
            the env variable 'CONAN_ERROR_ON_OVERRIDE'
        """
        with environment_append({'CONAN_ERROR_ON_OVERRIDE': "True"}):
            self._export("Hello3", "0.1",
                         ["Hello1/0.1@lasote/stable", "Hello2/0.1@lasote/stable",
                          "Hello0/0.1@lasote/stable"], export=False)
            self.client.run("install . --build missing", assert_error=True)
            self.assertIn("ERROR: Hello2/0.1@lasote/stable: requirement Hello0/0.2@lasote/stable"
                          " overridden by Hello3/0.1@None/None to Hello0/0.1@lasote/stable",
                          self.client.user_io.out)
