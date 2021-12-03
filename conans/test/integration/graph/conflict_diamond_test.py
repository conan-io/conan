import os
import textwrap
import unittest

import pytest

from conans.util.env import environment_update
from conans.paths import CONANFILE
from conans.test.utils.tools import TestClient, load
import json


@pytest.mark.xfail(reason="Conflict Output have changed")
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
            self.client.run("export . --user=lasote --channel=stable")

    def setUp(self):
        self.client = TestClient()
        self._export("hello0", "0.1")
        self._export("hello0", "0.2")
        self._export("hello1", "0.1", ["hello0/0.1@lasote/stable"])
        self._export("Hello2", "0.1", ["hello0/0.2@lasote/stable"])

    def test_conflict(self):
        """ There is a conflict in the graph: branches with requirement in different
            version, Conan will raise
        """
        self._export("Hello3", "0.1", ["hello1/0.1@lasote/stable", "hello2/0.1@lasote/stable"],
                     export=False)
        self.client.run("install . --build missing", assert_error=True)
        self.assertIn("Conflict in hello2/0.1@lasote/stable:\n"
                      "    'hello2/0.1@lasote/stable' requires 'hello0/0.2@lasote/stable' "
                      "while 'hello1/0.1@lasote/stable' requires 'hello0/0.1@lasote/stable'.\n"
                      "    To fix this conflict you need to override the package 'hello0' in "
                      "your root package.", self.client.out)
        self.assertNotIn("Generated conaninfo.txt", self.client.out)

    def test_override_silent(self):
        """ There is a conflict in the graph, but the consumer project depends on the conflicting
            library, so all the graph will use the version from the consumer project
        """
        self._export("Hello3", "0.1",
                     ["hello1/0.1@lasote/stable", "hello2/0.1@lasote/stable",
                      "hello0/0.1@lasote/stable"], export=False)
        self.client.run("install . --build missing", assert_error=False)
        self.assertIn("hello2/0.1@lasote/stable: requirement hello0/0.2@lasote/stable overridden"
                      " by Hello3/0.1 to hello0/0.1@lasote/stable",
                      self.client.out)


@pytest.mark.xfail(reason="UX conflict error to be completed")
def test_create_werror():
    client = TestClient()
    client.save({"conanfile.py": """from conans import ConanFile
class Pkg(ConanFile):
pass
    """})
    client.run("export . --name=LibA --version=0.1 --user=user --channel=channel")
    client.run("export conanfile.py --name=LibA --version=0.2 --user=user --channel=channel")
    client.save({"conanfile.py": """from conans import ConanFile
class Pkg(ConanFile):
requires = "LibA/0.1@user/channel"
    """})
    client.run("export ./ --name=LibB --version=0.1 --user=user --channel=channel")
    client.save({"conanfile.py": """from conans import ConanFile
class Pkg(ConanFile):
requires = "LibA/0.2@user/channel"
    """})
    client.run("export . --name=LibC --version=0.1 --user=user --channel=channel")
    client.save({"conanfile.py": """from conans import ConanFile
class Pkg(ConanFile):
requires = "LibB/0.1@user/channel", "LibC/0.1@user/channel"
    """})
    client.run("create ./conanfile.py consumer/0.1@lasote/testing", assert_error=True)
    self.assertIn("ERROR: Conflict in LibC/0.1@user/channel",
                  client.out)
