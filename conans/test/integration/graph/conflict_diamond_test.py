import os
import textwrap
import unittest

from conans.client.tools import environment_append
from conans.paths import CONANFILE
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient, load
import json


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
        self.assertIn("Conflict in Hello2/0.1@lasote/stable:\n"
                      "    'Hello2/0.1@lasote/stable' requires 'Hello0/0.2@lasote/stable' "
                      "while 'Hello1/0.1@lasote/stable' requires 'Hello0/0.1@lasote/stable'.\n"
                      "    To fix this conflict you need to override the package 'Hello0' in "
                      "your root package.", self.client.out)
        self.assertNotIn("Generated conaninfo.txt", self.client.out)

    def test_override_silent(self):
        """ There is a conflict in the graph, but the consumer project depends on the conflicting
            library, so all the graph will use the version from the consumer project
        """
        self._export("Hello3", "0.1",
                     ["Hello1/0.1@lasote/stable", "Hello2/0.1@lasote/stable",
                      "Hello0/0.1@lasote/stable"], export=False)
        self.client.run("install . --build missing", assert_error=False)
        self.assertIn("Hello2/0.1@lasote/stable: requirement Hello0/0.2@lasote/stable overridden"
                      " by Hello3/0.1 to Hello0/0.1@lasote/stable",
                      self.client.out)

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
                          " overridden by Hello3/0.1 to Hello0/0.1@lasote/stable",
                          self.client.out)

    def test_override_explicit(self):
        """ Given a conflict in dependencies that is overridden by the consumer project (with
            the explicit keyword 'override'), it won't raise because it is explicit, even if the
            user has set env variable 'CONAN_ERROR_ON_OVERRIDE' to True
        """
        with environment_append({'CONAN_ERROR_ON_OVERRIDE': "True"}):
            conanfile = self.conanfile % ("Hello3", "0.1",
                                          '(("Hello1/0.1@lasote/stable"), '
                                          '("Hello2/0.1@lasote/stable"), '
                                          '("Hello0/0.1@lasote/stable", "override"),)')
            self.client.save({CONANFILE: conanfile})
            self.client.run("install . --build missing")
            self.assertIn("Hello2/0.1@lasote/stable: requirement Hello0/0.2@lasote/stable overridden"
                          " by Hello3/0.1 to Hello0/0.1@lasote/stable",
                          self.client.out)

            # ...but there is no way to tell Conan that 'Hello3' wants to depend also on 'Hello0'.
            json_file = os.path.join(self.client.current_folder, 'tmp.json')
            self.client.run('info . --only=requires --json="{}"'.format(json_file))
            data = json.loads(load(json_file))
            hello0 = data[0]
            self.assertEqual(hello0["reference"], "Hello0/0.1@lasote/stable")
            self.assertListEqual(sorted(hello0["required_by"]),
                                 sorted(["Hello2/0.1@lasote/stable", "Hello1/0.1@lasote/stable"]))


def test_conflict_msg():
    c = TestClient()
    c.save({"lib/conanfile.py": GenConanfile(),
            "conanfile.txt":  textwrap.dedent("""
                                [requires]
                                libdeflate/1.7
                                [build_requires]
                                libdeflate/1.8
                                """)})
    c.run("export lib libdeflate/1.7@")
    c.run("export lib libdeflate/1.8@")
    c.run("install .", assert_error=True)
    assert "ERROR: Unresolvable conflict between libdeflate/1.7 and libdeflate/1.8" in c.out
